package com.inad.stocks.service;

import com.inad.stocks.dto.ClosedPositionInfo;
import com.inad.stocks.dto.ExtendedPositionInfo;
import com.inad.stocks.dto.OpenedPositionInfo;
import com.inad.stocks.dto.PositionDTO;
import com.inad.stocks.dto.ReducedPositionInfo;
import com.inad.stocks.entity.MidTradeReflection;
import com.inad.stocks.entity.Position;
import com.inad.stocks.entity.TraderState;
import com.inad.stocks.repository.MidTradeReflectionRepository;
import com.inad.stocks.integration.broker.StockBrokerClient;
import com.inad.stocks.integration.grok.GrokService;
import com.inad.stocks.integration.grok.dto.AnalysisResult;
import com.inad.stocks.integration.grok.dto.NewOpportunity;
import com.inad.stocks.integration.grok.dto.PositionDecision;
import com.inad.stocks.repository.PositionRepository;
import com.inad.stocks.repository.TraderStateRepository;
import com.inad.stocks.websocket.EquityWebSocketHandler;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import org.springframework.transaction.annotation.Transactional;
import com.inad.stocks.service.MarketHoursService;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Portfolio Manager Service - Main orchestrator for trading cycles.
 * 
 * Responsibilities:
 * 1. Build context for Grok analysis (positions, deployment status)
 * 2. Call GrokService for AI-powered recommendations
 * 3. Execute position decisions (KEEP, CLOSE, EXTEND, REDUCE)
 * 4. Open new positions based on opportunities
 * 5. Update trader state and broadcast updates
 * 
 * This service contains all the business logic for portfolio management,
 * keeping the scheduler focused only on timing.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PortfolioManagerService {

    private final GrokService grokService;
    private final PositionService positionService;
    private final StockBrokerClient stockBrokerClient;
    private final TraderStateRepository traderStateRepository;
    private final EquityWebSocketHandler equityWebSocketHandler;
    private final AuditService auditService;
    private final AccountingService accountingService;
    private final LogbookService logbookService;
    private final PositionRepository positionRepository;
    private final FeeService feeService;
    private final MarketHoursService marketHoursService;
    
    @Autowired(required = false)
    private SelfReflectionService selfReflectionService;
    
    @Autowired(required = false)
    private OpenPositionEvaluator openPositionEvaluator;
    
    @Autowired(required = false)
    private MidTradeReflectionRepository midTradeReflectionRepository;

    // Position sizing and count are determined dynamically by Grok AI
    
    @Value("${trading.deployment.min-ratio:0.75}")
    private BigDecimal minDeploymentRatio;

    @Value("${trading.deployment.max-ratio:0.90}")
    private BigDecimal maxDeploymentRatio;

    @Value("${trading.conviction.min-threshold:60}")
    private int minConvictionThreshold;

    private final AtomicBoolean running = new AtomicBoolean(false);
    private final AtomicInteger cycleNumber = new AtomicInteger(0);

    /**
     * Run a complete trading cycle.
     * 
     * @return CycleResult with statistics about the cycle
     */
    @Transactional
    public CycleResult runCycle() {
        // Check market hours BEFORE acquiring the lock
        if (!marketHoursService.isTradingAllowed()) {
            MarketHoursService.MarketStatus status = marketHoursService.getMarketStatus();
            log.info("Market is closed ({}). Skipping trading cycle. {}", 
                    status.status(), status.detail());
            return CycleResult.skipped("Market closed: " + status.description());
        }
        
        if (!running.compareAndSet(false, true)) {
            log.warn("Previous trading cycle still running, skipping");
            return CycleResult.skipped("Previous cycle still running");
        }

        int currentCycle = cycleNumber.incrementAndGet();
        long nextCycleAt = Instant.now().plusSeconds(600).getEpochSecond();
        CycleResult.CycleResultBuilder resultBuilder = CycleResult.builder().cycleNumber(currentCycle);

        try {
            log.info("═══════════════════════════════════════════════════════════════════");
            log.info("Starting Trading Cycle #{}", currentCycle);
            log.info("═══════════════════════════════════════════════════════════════════");

            broadcastPhase("analyzing", nextCycleAt, currentCycle);

            // 1. Get current state
            TraderState state = traderStateRepository.getOrCreateMain();
            List<PositionDTO> openPositions = positionService.getOpenPositions();

            log.info("Current state: {} open positions, capital: {}",
                    openPositions.size(), state.getCurrentCapital());

            resultBuilder.openPositionsBefore(openPositions.size())
                    .availableCapital(state.getCurrentCapital());

            // 1b. Evaluate open positions against Pre-Mortem predictions
            String healthContext = "";
            if (openPositionEvaluator != null && !openPositions.isEmpty()) {
                List<OpenPositionEvaluator.PositionHealthCheck> healthChecks = 
                        openPositionEvaluator.evaluateOpenPositions();
                
                if (!healthChecks.isEmpty()) {
                    // Store mid-trade reflections
                    storeMidTradeReflections(healthChecks, currentCycle);
                    
                    // Build health context for Grok
                    healthContext = openPositionEvaluator.buildHealthContext(healthChecks);
                    
                    // Log summary
                    long dangerCount = healthChecks.stream()
                            .filter(h -> h.getHealthStatus() == OpenPositionEvaluator.PositionHealthCheck.HealthStatus.DANGER)
                            .count();
                    long warningCount = healthChecks.stream()
                            .filter(h -> h.getHealthStatus() == OpenPositionEvaluator.PositionHealthCheck.HealthStatus.WARNING)
                            .count();
                    
                    if (dangerCount > 0 || warningCount > 0) {
                        log.warn("Pre-Mortem Health Check: {} DANGER, {} WARNING, {} HEALTHY",
                                dangerCount, warningCount, healthChecks.size() - dangerCount - warningCount);
                    } else {
                        log.info("Pre-Mortem Health Check: All {} positions within expectations", healthChecks.size());
                    }
                }
            }

            // 2. Build context for Grok
            String positionsContext = buildPositionsContext(openPositions);
            String deploymentInfo = buildDeploymentInfo(state, openPositions);

            // 3. Get AI analysis (including Pre-Mortem health context)
            // Grok decides how many positions to open based on market conditions
            AnalysisResult analysis = grokService.analyze(
                    positionsContext + healthContext,
                    deploymentInfo,
                    state.getCurrentCapital()
            );

            if (!analysis.isSuccessful()) {
                log.warn("Analysis failed: {}", analysis.getError());
                broadcastPhase("idle", nextCycleAt, currentCycle);
                return resultBuilder.error(analysis.getError()).build();
            }

            log.info("Grok analysis: {} coins analyzed, {} skipped",
                    analysis.getStocksAnalyzed(), analysis.getStocksSkipped());
            log.info("Market summary: {}", analysis.getMarketSummary());

            resultBuilder.stocksAnalyzed(analysis.getStocksAnalyzed())
                    .marketSummary(analysis.getMarketSummary());

            // 4. Execute trading phase
            broadcastPhase("trading", nextCycleAt, currentCycle);

            // Track actions for logbook
            List<ClosedPositionInfo> closedPositions = new ArrayList<>();
            List<OpenedPositionInfo> openedPositions = new ArrayList<>();
            List<String> keptPositions = new ArrayList<>();
            List<ExtendedPositionInfo> extendedPositions = new ArrayList<>();
            List<ReducedPositionInfo> reducedPositions = new ArrayList<>();

            // 4a. Process position decisions (CLOSE, EXTEND, REDUCE)
            processPositionDecisions(analysis, state, closedPositions, keptPositions, extendedPositions, reducedPositions);
            resultBuilder.positionsClosed(closedPositions.size());

            // 4b. Open new positions (Grok decides how many)
            processNewOpportunities(analysis, state, openedPositions);
            resultBuilder.positionsOpened(openedPositions.size());

            // 5. Update state
            state.setTotalCycles(state.getTotalCycles() + 1);
            state.setLastCycleAt(Instant.now());
            traderStateRepository.save(state);

            // 6. Calculate current portfolio state for logbook
            List<PositionDTO> updatedPositions = positionService.getOpenPositions();
            BigDecimal cashBalance = accountingService.getCashBalance();
            BigDecimal positionsValue = updatedPositions.stream()
                    .map(PositionDTO::getSizeUsd)
                    .reduce(BigDecimal.ZERO, BigDecimal::add);
            BigDecimal unrealizedPnl = updatedPositions.stream()
                    .map(p -> p.getUnrealizedPnl() != null ? p.getUnrealizedPnl() : BigDecimal.ZERO)
                    .reduce(BigDecimal.ZERO, BigDecimal::add);
            BigDecimal totalEquity = cashBalance.add(positionsValue).add(unrealizedPnl);
            BigDecimal deploymentPercent = totalEquity.compareTo(BigDecimal.ZERO) > 0
                    ? positionsValue.divide(totalEquity, 4, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                    : BigDecimal.ZERO;

            // 7. Log to logbook
            logbookService.log(
                    analysis,
                    closedPositions,
                    openedPositions,
                    keptPositions,
                    extendedPositions,
                    reducedPositions,
                    totalEquity,
                    unrealizedPnl,
                    updatedPositions.size(),
                    deploymentPercent
            );

            // 8. Log audit
            auditService.logSystemEvent("CYCLE_COMPLETE",
                    String.format("Cycle #%d: Closed %d, Opened %d, Analyzed %d coins",
                            currentCycle, closedPositions.size(), openedPositions.size(), analysis.getStocksAnalyzed()));

            log.info("═══════════════════════════════════════════════════════════════════");
            log.info("Trading Cycle #{} Complete - Closed: {}, Opened: {}",
                    currentCycle, closedPositions.size(), openedPositions.size());
            log.info("═══════════════════════════════════════════════════════════════════");

            return resultBuilder.success(true).build();

        } catch (Exception e) {
            log.error("Trading cycle failed: {}", e.getMessage(), e);
            auditService.logSystemEvent("CYCLE_ERROR",
                    String.format("Cycle #%d failed: %s", currentCycle, e.getMessage()));
            return resultBuilder.error(e.getMessage()).build();

        } finally {
            running.set(false);
            broadcastPhase("idle", nextCycleAt, currentCycle);
        }
    }

    /**
     * Process position decisions from Grok analysis.
     * Handles CLOSE, EXTEND, REDUCE, and KEEP actions.
     * Populates the lists for logbook tracking.
     */
    private void processPositionDecisions(AnalysisResult analysis, TraderState state,
                                          List<ClosedPositionInfo> closedPositions,
                                          List<String> keptPositions,
                                          List<ExtendedPositionInfo> extendedPositions,
                                          List<ReducedPositionInfo> reducedPositions) {

        for (PositionDecision decision : analysis.getPositionDecisions()) {
            log.info("Position decision: {} {} (sentiment: {})",
                    decision.getAction(), decision.getSymbol(), decision.getCurrentSentiment());

            switch (decision.getAction()) {
                case CLOSE -> {
                    ClosedPositionInfo info = closePosition(decision.getSymbol(), decision.getReason(), state);
                    if (info != null) {
                        closedPositions.add(info);
                    }
                }
                case EXTEND -> {
                    ExtendedPositionInfo info = extendPosition(decision.getSymbol(), decision.getScalePercent(), decision.getReason(), state);
                    if (info != null) {
                        extendedPositions.add(info);
                    }
                }
                case REDUCE -> {
                    ReducedPositionInfo info = reducePosition(decision.getSymbol(), decision.getScalePercent(), decision.getReason(), state);
                    if (info != null) {
                        reducedPositions.add(info);
                    }
                }
                case KEEP -> {
                    keptPositions.add(decision.getSymbol());
                    log.debug("Keeping position {}: {}", decision.getSymbol(), decision.getReason());
                }
            }
        }
    }

    /**
     * Process new opportunities from Grok analysis.
     * Opens new positions for high-conviction trades.
     * Grok decides how many positions to open - no artificial limits.
     * Populates openedPositions list for logbook tracking.
     */
    private void processNewOpportunities(AnalysisResult analysis, TraderState state, 
                                         List<OpenedPositionInfo> openedPositions) {

        for (NewOpportunity opportunity : analysis.getOpportunitiesByConviction()) {
            if (!opportunity.meetsConvictionThreshold(minConvictionThreshold)) {
                log.debug("Skipping {} - conviction {} below threshold {}",
                        opportunity.getSymbol(), opportunity.getConviction(), minConvictionThreshold);
                continue;
            }

            log.info("New opportunity: {} {} (conviction: {})",
                    opportunity.getDirection(), opportunity.getSymbol(),
                    opportunity.getConviction());

            OpenedPositionInfo info = openNewPosition(opportunity, state);
            if (info != null) {
                openedPositions.add(info);
            }
        }
    }

    private ClosedPositionInfo closePosition(String symbol, String reason, TraderState state) {
        try {
            PositionDTO position = positionService.getPositionBySymbol(symbol);
            if (position == null) {
                log.warn("Cannot close {} - position not found", symbol);
                return null;
            }

            BigDecimal currentPrice = stockBrokerClient.getPrice(symbol);
            if (currentPrice.compareTo(BigDecimal.ZERO) == 0) {
                log.warn("Cannot close {} - failed to get price", symbol);
                return null;
            }

            // Calculate exit fee using FeeService (respects VIP tier)
            BigDecimal exitFee = feeService.calculateTakerFee(position.getSizeUsd());

            // Get Position entity for reflection (before closing)
            Position positionEntity = positionRepository.findById(position.getId()).orElse(null);

            // Close the position (accounting is handled in PositionService)
            positionService.closePosition(position.getId(), currentPrice, reason, exitFee);

            // Calculate PnL
            BigDecimal pnl = calculatePnL(position, currentPrice);
            BigDecimal pnlPercent = position.getSizeUsd().compareTo(BigDecimal.ZERO) > 0
                    ? pnl.divide(position.getSizeUsd(), 4, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                    : BigDecimal.ZERO;

            log.info("Closed {} @ {} - PnL: {} - Reason: {}",
                    symbol, currentPrice, pnl, reason);
            
            // Trigger self-reflection for learning (async-like, non-blocking)
            if (selfReflectionService != null && positionEntity != null) {
                try {
                    // Update exit time on entity for reflection
                    positionEntity.setExitTime(Instant.now());
                    selfReflectionService.reflectOnTrade(positionEntity, currentPrice, 
                            "Exit reason: " + reason + ". PnL: " + pnlPercent + "%");
                } catch (Exception e) {
                    log.warn("Self-reflection failed for {}: {}", symbol, e.getMessage());
                }
            }
            
            return ClosedPositionInfo.builder()
                    .symbol(symbol)
                    .direction(position.getDirection())
                    .entryPrice(position.getEntryPrice())
                    .exitPrice(currentPrice)
                    .pnl(pnl)
                    .pnlPercent(pnlPercent)
                    .reason(reason)
                    .build();

        } catch (Exception e) {
            log.error("Failed to close position {}: {}", symbol, e.getMessage());
            return null;
        }
    }

    private ExtendedPositionInfo extendPosition(String symbol, int scalePercent, String reason, TraderState state) {
        try {
            PositionDTO position = positionService.getPositionBySymbol(symbol);
            if (position == null) {
                log.warn("Cannot extend {} - position not found", symbol);
                return null;
            }

            // Calculate extension size
            BigDecimal extensionSize = position.getSizeUsd()
                    .multiply(BigDecimal.valueOf(scalePercent))
                    .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP);

            // Check if we have enough capital
            BigDecimal availableCash = accountingService.getCashBalance();
            if (extensionSize.compareTo(availableCash) > 0) {
                log.warn("Cannot extend {} - insufficient capital (need {}, have {})", 
                        symbol, extensionSize, availableCash);
                return null;
            }

            // Execute the extension via PositionService
            PositionService.ExtendResult result = positionService.extendPosition(
                    position.getId(), extensionSize, reason);

            if (!result.isSuccess()) {
                log.warn("Failed to extend {}: {}", symbol, result.getError());
                return null;
            }

            log.info("Extended {} by {}% ({} USD) @ {} - Reason: {}",
                    symbol, scalePercent, extensionSize, result.getPrice(), reason);

            return ExtendedPositionInfo.builder()
                    .symbol(symbol)
                    .scalePercent(scalePercent)
                    .addedSize(result.getAddedSize())
                    .price(result.getPrice())
                    .reason(reason)
                    .build();

        } catch (Exception e) {
            log.error("Failed to extend position {}: {}", symbol, e.getMessage());
            return null;
        }
    }

    private ReducedPositionInfo reducePosition(String symbol, int scalePercent, String reason, TraderState state) {
        try {
            PositionDTO position = positionService.getPositionBySymbol(symbol);
            if (position == null) {
                log.warn("Cannot reduce {} - position not found", symbol);
                return null;
            }

            // Execute the reduction via PositionService
            PositionService.ReduceResult result = positionService.reducePosition(
                    position.getId(), scalePercent, reason);

            if (!result.isSuccess()) {
                log.warn("Failed to reduce {}: {}", symbol, result.getError());
                return null;
            }

            log.info("Reduced {} by {}% ({} USD) @ {} - PnL: {} - Reason: {}",
                    symbol, scalePercent, result.getReducedSize(), result.getPrice(), 
                    result.getPartialPnl(), reason);

            return ReducedPositionInfo.builder()
                    .symbol(symbol)
                    .scalePercent(scalePercent)
                    .reducedSize(result.getReducedSize())
                    .price(result.getPrice())
                    .partialPnl(result.getPartialPnl())
                    .reason(reason)
                    .build();

        } catch (Exception e) {
            log.error("Failed to reduce position {}: {}", symbol, e.getMessage());
            return null;
        }
    }

    private OpenedPositionInfo openNewPosition(NewOpportunity opportunity, TraderState state) {
        try {
            String symbol = opportunity.getSymbol().toUpperCase();
            // For stocks, we use the raw symbol (e.g., AAPL, NVDA) without any suffix

            // Check if we already have this position
            if (positionService.getPositionBySymbol(symbol) != null) {
                log.warn("Already have position in {}, skipping", symbol);
                return null;
            }

            BigDecimal price = stockBrokerClient.getPrice(symbol);
            if (price.compareTo(BigDecimal.ZERO) == 0) {
                log.warn("Failed to get price for {}, skipping", symbol);
                return null;
            }

            // Get available cash from accounting ledger
            BigDecimal availableCash = accountingService.getCashBalance();

            // Position size determined by Grok - NO FIXED LIMITS
            // Grok provides position_size_percent (1-100%) based on conviction
            BigDecimal sizePercent;
            if (opportunity.getPositionSizePercent() != null && opportunity.getPositionSizePercent() > 0) {
                // Use Grok's recommended size (1-100% of available capital)
                sizePercent = BigDecimal.valueOf(opportunity.getPositionSizePercent())
                        .divide(BigDecimal.valueOf(100), 4, RoundingMode.HALF_UP);
                log.info("Using Grok-determined position size: {}% for {} (conviction: {})", 
                        opportunity.getPositionSizePercent(), symbol, opportunity.getConviction());
            } else {
                // Fallback: use conviction-based sizing if Grok didn't provide size
                // High conviction (80+) = 30%, Medium (60-79) = 15%
                sizePercent = opportunity.getConviction() >= 80 
                        ? BigDecimal.valueOf(0.30) 
                        : BigDecimal.valueOf(0.15);
                log.info("Fallback position size: {}% for {} (conviction: {})", 
                        sizePercent.multiply(BigDecimal.valueOf(100)), symbol, opportunity.getConviction());
            }

            BigDecimal sizeUsdt = availableCash
                    .multiply(sizePercent)
                    .setScale(2, RoundingMode.HALF_UP);

            // Only check if we have enough cash - no artificial upper limit
            if (sizeUsdt.compareTo(availableCash) > 0) {
                sizeUsdt = availableCash; // Use all available if requested more
                log.info("Adjusted position size to available cash: {} USD", sizeUsdt);
            }

            // Minimum position size check
            if (sizeUsdt.compareTo(BigDecimal.valueOf(10)) < 0) {
                log.warn("Position size too small for {}: {} USD", symbol, sizeUsdt);
                return null;
            }

            String direction = opportunity.getDirection().name();

            // Open position via paper trading
            StockBrokerClient.TradeResult result = stockBrokerClient.openPosition(
                    symbol,
                    direction,
                    sizeUsdt
            );

            if (result.isSuccess()) {
                // Create position in DB with Pre-Mortem data
                Position position = positionService.createPosition(
                        symbol,
                        direction,
                        result.getPrice(),
                        result.getQuantity(),
                        sizeUsdt,
                        opportunity.getConviction(),
                        opportunity.getReason(),
                        opportunity.getPreMortem(),
                        opportunity.getBullCase(),
                        opportunity.getBearCase(),
                        opportunity.getExpectedHoldHoursMin(),
                        opportunity.getExpectedHoldHoursMax(),
                        opportunity.getTargetPnlPercent(),
                        opportunity.getMaxAcceptableLossPercent()
                );

                // Record in accounting ledger (double-entry bookkeeping)
                accountingService.recordOpenPosition(
                        position.getId(),
                        symbol,
                        sizeUsdt,
                        result.getFee(),
                        result.getSpread(),
                        result.getSlippage(),
                        result.getPrice(),
                        direction
                );

                // Update statistics in trader state (for reporting only, not for capital tracking)
                state.setTotalFeesPaid(state.getTotalFeesPaid().add(result.getFee()));

                log.info("Opened {} {} @ {} (conviction: {}, size: {} USD = {}% of available)",
                        direction, symbol, result.getPrice(),
                        opportunity.getConviction(), sizeUsdt, 
                        sizePercent.multiply(BigDecimal.valueOf(100)).setScale(0, RoundingMode.HALF_UP));
                
                return OpenedPositionInfo.builder()
                        .symbol(symbol)
                        .direction(direction)
                        .entryPrice(result.getPrice())
                        .sizeUsd(sizeUsdt)
                        .conviction(opportunity.getConviction())
                        .reason(opportunity.getReason())
                        .build();
            }

            return null;

        } catch (Exception e) {
            log.error("Failed to open position for {}: {}", opportunity.getSymbol(), e.getMessage());
            return null;
        }
    }

    private BigDecimal calculatePnL(PositionDTO position, BigDecimal currentPrice) {
        BigDecimal entryPrice = position.getEntryPrice();
        BigDecimal quantity = position.getQuantity();

        BigDecimal priceDiff;
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            priceDiff = currentPrice.subtract(entryPrice);
        } else {
            priceDiff = entryPrice.subtract(currentPrice);
        }

        return priceDiff.multiply(quantity).setScale(2, RoundingMode.HALF_UP);
    }

    /**
     * Build formatted context string for open positions.
     */
    private String buildPositionsContext(List<PositionDTO> positions) {
        if (positions.isEmpty()) {
            return "OFFENE POSITIONEN: Keine";
        }

        StringBuilder sb = new StringBuilder("OFFENE POSITIONEN:\n");
        for (PositionDTO p : positions) {
            BigDecimal currentPrice = stockBrokerClient.getPrice(p.getSymbol());
            BigDecimal pnl = calculatePnL(p, currentPrice);
            BigDecimal pnlPercent = p.getSizeUsd().compareTo(BigDecimal.ZERO) > 0
                    ? pnl.divide(p.getSizeUsd(), 4, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                    : BigDecimal.ZERO;

            Duration holdTime = Duration.between(p.getEntryTime(), Instant.now());
            String holdTimeStr = formatDuration(holdTime);

            // Risk assessment
            String riskLevel = assessRisk(pnlPercent, holdTime);

            sb.append(String.format("- %s: %s @ %s → %s (PnL: %s%%, Haltezeit: %s) %s\n",
                    p.getSymbol(),
                    p.getDirection(),
                    p.getEntryPrice(),
                    currentPrice,
                    pnlPercent.setScale(2, RoundingMode.HALF_UP),
                    holdTimeStr,
                    riskLevel));
            
            // Add YOUR TARGETS line if Pre-Mortem data is available
            if (p.getTargetPnlPercent() != null && p.getMaxAcceptableLossPercent() != null) {
                BigDecimal progressPercent = p.getTargetPnlPercent().compareTo(BigDecimal.ZERO) != 0
                        ? pnlPercent.divide(p.getTargetPnlPercent(), 1, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                        : BigDecimal.ZERO;
                
                String holdRange = (p.getExpectedHoldHoursMin() != null && p.getExpectedHoldHoursMax() != null)
                        ? String.format("%d-%dh", p.getExpectedHoldHoursMin(), p.getExpectedHoldHoursMax())
                        : "n/a";
                
                sb.append(String.format("  📊 YOUR TARGETS: Target +%s%% | Stop -%s%% | Hold %s | Progress: %s%%\n",
                        p.getTargetPnlPercent().setScale(1, RoundingMode.HALF_UP),
                        p.getMaxAcceptableLossPercent().setScale(1, RoundingMode.HALF_UP),
                        holdRange,
                        progressPercent.setScale(0, RoundingMode.HALF_UP)));
            }
        }

        return sb.toString();
    }

    private String assessRisk(BigDecimal pnlPercent, Duration holdTime) {
        // First check: TOO EARLY warning for young positions (unless catastrophic loss)
        if (holdTime.toHours() < 24 && pnlPercent.compareTo(BigDecimal.valueOf(-25)) > 0) {
            return "⏳ TOO EARLY TO JUDGE - minimum 24h before considering close!";
        }
        
        // Critical loss takes priority regardless of hold time
        if (pnlPercent.compareTo(BigDecimal.valueOf(-25)) < 0) {
            return "🔴 DANGER: Critical loss";
        } else if (pnlPercent.compareTo(BigDecimal.valueOf(-15)) < 0) {
            return "🟡 WARNING: Heavy loss";
        } else if (holdTime.toHours() > 336) {  // 2 weeks - stocks need time!
            return "🟠 STALE: Consider rotation";
        } else if (pnlPercent.compareTo(BigDecimal.valueOf(40)) > 0) {
            return "💰 PROFIT: Consider taking gains";
        }
        return "";
    }

    private String formatDuration(Duration duration) {
        long hours = duration.toHours();
        if (hours < 1) {
            return duration.toMinutes() + "m";
        } else if (hours < 24) {
            return hours + "h";
        } else {
            return duration.toDays() + "d";
        }
    }

    /**
     * Build deployment info string for Grok context.
     * Grok decides how many positions to hold - no artificial limits.
     */
    private String buildDeploymentInfo(TraderState state, List<PositionDTO> positions) {
        BigDecimal positionsValue = positions.stream()
                .map(PositionDTO::getSizeUsd)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal totalEquity = state.getCurrentCapital().add(positionsValue);
        BigDecimal deploymentRatio = totalEquity.compareTo(BigDecimal.ZERO) > 0
                ? positionsValue.divide(totalEquity, 4, RoundingMode.HALF_UP)
                : BigDecimal.ZERO;

        String status;
        if (deploymentRatio.compareTo(minDeploymentRatio) < 0) {
            status = "⚠️ BELOW TARGET - Consider opening more positions";
        } else if (deploymentRatio.compareTo(maxDeploymentRatio) > 0) {
            status = "⚠️ HIGHLY DEPLOYED - Be selective with new positions";
        } else {
            status = "✅ In target range";
        }

        return String.format("DEPLOYMENT: %.1f%% (Target: %.0f%%-%.0f%%) %s\nAvailable capital: %s USD\nOpen positions: %d",
                deploymentRatio.multiply(BigDecimal.valueOf(100)),
                minDeploymentRatio.multiply(BigDecimal.valueOf(100)),
                maxDeploymentRatio.multiply(BigDecimal.valueOf(100)),
                status,
                state.getCurrentCapital(),
                positions.size());
    }

    /**
     * Store mid-trade reflections for learning analysis.
     */
    private void storeMidTradeReflections(List<OpenPositionEvaluator.PositionHealthCheck> healthChecks, int cycleNum) {
        if (midTradeReflectionRepository == null) {
            return;
        }
        
        for (OpenPositionEvaluator.PositionHealthCheck check : healthChecks) {
            MidTradeReflection reflection = MidTradeReflection.builder()
                    .id(java.util.UUID.randomUUID().toString())
                    .positionId(check.getPositionId())
                    .symbol(check.getSymbol())
                    .direction(check.getDirection())
                    .evaluatedAt(Instant.now())
                    .currentPrice(check.getCurrentPrice())
                    .currentPnlPercent(check.getCurrentPnlPercent())
                    .currentHoldHours(check.getCurrentHoldHours())
                    .targetPnlPercent(check.getTargetPnlPercent())
                    .maxAcceptableLoss(check.getMaxAcceptableLoss())
                    .expectedHoldHoursMax(check.getExpectedHoldHoursMax())
                    .withinPnlExpectations(check.isWithinPnlExpectations())
                    .withinTimeExpectations(check.isWithinTimeExpectations())
                    .approachingMaxLoss(check.isApproachingMaxLoss())
                    .exceedingTarget(check.isExceedingTargetPnl())
                    .healthStatus(MidTradeReflection.HealthStatus.valueOf(check.getHealthStatus().name()))
                    .recommendation(check.getRecommendation())
                    .healthReason(check.getHealthReason())
                    .preMortem(check.getPreMortem())
                    .bearCase(check.getBearCase())
                    .cycleNumber(cycleNum)
                    .build();
            
            midTradeReflectionRepository.save(reflection);
        }
        
        log.debug("Stored {} mid-trade reflections for cycle #{}", healthChecks.size(), cycleNum);
    }

    private void broadcastPhase(String phase, long nextCycleAt, int cycleNumber) {
        equityWebSocketHandler.broadcastPhase(phase, nextCycleAt, cycleNumber);
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // PUBLIC GETTERS
    // ═══════════════════════════════════════════════════════════════════════════════

    public boolean isRunning() {
        return running.get();
    }

    public int getCurrentCycleNumber() {
        return cycleNumber.get();
    }

    /**
     * Check if trading is currently allowed based on market hours.
     */
    public boolean isTradingAllowed() {
        return marketHoursService.isTradingAllowed();
    }

    /**
     * Get current market status for UI display.
     */
    public MarketHoursService.MarketStatus getMarketStatus() {
        return marketHoursService.getMarketStatus();
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // CYCLE RESULT
    // ═══════════════════════════════════════════════════════════════════════════════

    /**
     * Result of a trading cycle execution.
     */
    @lombok.Data
    @lombok.Builder
    public static class CycleResult {
        private int cycleNumber;
        private boolean success;
        private boolean skipped;
        private boolean marketClosed;
        private String error;
        private String marketSummary;
        private int openPositionsBefore;
        private int positionsClosed;
        private int positionsOpened;
        private int stocksAnalyzed;
        private BigDecimal availableCapital;

        public static CycleResult skipped(String reason) {
            boolean isMarketClosed = reason != null && reason.toLowerCase().contains("market closed");
            return CycleResult.builder()
                    .skipped(true)
                    .marketClosed(isMarketClosed)
                    .error(reason)
                    .build();
        }
    }
}

