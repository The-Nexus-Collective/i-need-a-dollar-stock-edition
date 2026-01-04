package com.trading.service;

import com.trading.dto.ClosedPositionInfo;
import com.trading.dto.OpenedPositionInfo;
import com.trading.dto.PositionDTO;
import com.trading.entity.Position;
import com.trading.entity.TraderState;
import com.trading.integration.binance.BinanceClient;
import com.trading.integration.grok.GrokService;
import com.trading.integration.grok.dto.AnalysisResult;
import com.trading.integration.grok.dto.NewOpportunity;
import com.trading.integration.grok.dto.PositionDecision;
import com.trading.repository.TraderStateRepository;
import com.trading.websocket.EquityWebSocketHandler;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import org.springframework.transaction.annotation.Transactional;

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
    private final BinanceClient binanceClient;
    private final TraderStateRepository traderStateRepository;
    private final EquityWebSocketHandler equityWebSocketHandler;
    private final AuditService auditService;
    private final AccountingService accountingService;
    private final LogbookService logbookService;

    @Value("${trading.position.size-percent:0.02}")
    private BigDecimal positionSizePercent;

    @Value("${trading.position.max-positions:50}")
    private int maxPositions;

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
            int availableSlots = maxPositions - openPositions.size();

            log.info("Current state: {} open positions, {} available slots, capital: {}",
                    openPositions.size(), availableSlots, state.getCurrentCapital());

            resultBuilder.openPositionsBefore(openPositions.size())
                    .availableCapital(state.getCurrentCapital());

            // 2. Build context for Grok
            String positionsContext = buildPositionsContext(openPositions);
            String deploymentInfo = buildDeploymentInfo(state, openPositions);

            // 3. Get AI analysis
            AnalysisResult analysis = grokService.analyze(
                    positionsContext,
                    availableSlots,
                    deploymentInfo,
                    state.getCurrentCapital()
            );

            if (!analysis.isSuccessful()) {
                log.warn("Analysis failed: {}", analysis.getError());
                broadcastPhase("idle", nextCycleAt, currentCycle);
                return resultBuilder.error(analysis.getError()).build();
            }

            log.info("Grok analysis: {} coins analyzed, {} skipped",
                    analysis.getCoinsAnalyzed(), analysis.getCoinsSkipped());
            log.info("Market summary: {}", analysis.getMarketSummary());

            resultBuilder.coinsAnalyzed(analysis.getCoinsAnalyzed())
                    .marketSummary(analysis.getMarketSummary());

            // 4. Execute trading phase
            broadcastPhase("trading", nextCycleAt, currentCycle);

            // Track actions for logbook
            List<ClosedPositionInfo> closedPositions = new ArrayList<>();
            List<OpenedPositionInfo> openedPositions = new ArrayList<>();
            List<String> keptPositions = new ArrayList<>();
            List<String> extendedPositions = new ArrayList<>();
            List<String> reducedPositions = new ArrayList<>();

            // 4a. Process position decisions (CLOSE, EXTEND, REDUCE)
            processPositionDecisions(analysis, state, closedPositions, keptPositions, extendedPositions, reducedPositions);
            resultBuilder.positionsClosed(closedPositions.size());

            // 4b. Open new positions
            processNewOpportunities(analysis, state, availableSlots + closedPositions.size(), openedPositions);
            resultBuilder.positionsOpened(openedPositions.size());

            // 5. Update state
            state.setTotalCycles(state.getTotalCycles() + 1);
            state.setLastCycleAt(Instant.now());
            traderStateRepository.save(state);

            // 6. Calculate current portfolio state for logbook
            List<PositionDTO> updatedPositions = positionService.getOpenPositions();
            BigDecimal cashBalance = accountingService.getCashBalance();
            BigDecimal positionsValue = updatedPositions.stream()
                    .map(PositionDTO::getSizeUsdt)
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
                            currentCycle, closedPositions.size(), openedPositions.size(), analysis.getCoinsAnalyzed()));

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
                                          List<String> extendedPositions,
                                          List<String> reducedPositions) {

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
                    if (extendPosition(decision.getSymbol(), decision.getScalePercent(), decision.getReason(), state)) {
                        extendedPositions.add(decision.getSymbol());
                    }
                }
                case REDUCE -> {
                    if (reducePosition(decision.getSymbol(), decision.getScalePercent(), decision.getReason(), state)) {
                        reducedPositions.add(decision.getSymbol());
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
     * Populates openedPositions list for logbook tracking.
     */
    private void processNewOpportunities(AnalysisResult analysis, TraderState state, 
                                         int availableSlots, List<OpenedPositionInfo> openedPositions) {

        for (NewOpportunity opportunity : analysis.getOpportunitiesByConviction()) {
            if (availableSlots <= 0) {
                log.info("No more slots available, skipping remaining opportunities");
                break;
            }

            if (!opportunity.meetsConvictionThreshold(minConvictionThreshold)) {
                log.debug("Skipping {} - conviction {} below threshold {}",
                        opportunity.getSymbol(), opportunity.getConviction(), minConvictionThreshold);
                continue;
            }

            log.info("New opportunity: {} {} (conviction: {}, leverage: {})",
                    opportunity.getDirection(), opportunity.getSymbol(),
                    opportunity.getConviction(), opportunity.getLeverage());

            OpenedPositionInfo info = openNewPosition(opportunity, state);
            if (info != null) {
                openedPositions.add(info);
                availableSlots--;
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

            BigDecimal currentPrice = binanceClient.getPrice(symbol);
            if (currentPrice.compareTo(BigDecimal.ZERO) == 0) {
                log.warn("Cannot close {} - failed to get price", symbol);
                return null;
            }

            // Calculate exit fee
            BigDecimal exitFee = position.getSizeUsdt()
                    .multiply(new BigDecimal("0.001")) // 0.1% fee
                    .setScale(8, RoundingMode.HALF_UP);

            // Close the position (accounting is handled in PositionService)
            positionService.closePosition(position.getId(), currentPrice, reason, exitFee);

            // Calculate PnL
            BigDecimal pnl = calculatePnL(position, currentPrice);
            BigDecimal pnlPercent = position.getSizeUsdt().compareTo(BigDecimal.ZERO) > 0
                    ? pnl.divide(position.getSizeUsdt(), 4, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                    : BigDecimal.ZERO;

            log.info("Closed {} @ {} - PnL: {} - Reason: {}",
                    symbol, currentPrice, pnl, reason);
            
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

    private boolean extendPosition(String symbol, int scalePercent, String reason, TraderState state) {
        try {
            PositionDTO position = positionService.getPositionBySymbol(symbol);
            if (position == null) {
                log.warn("Cannot extend {} - position not found", symbol);
                return false;
            }

            BigDecimal currentPrice = binanceClient.getPrice(symbol);
            if (currentPrice.compareTo(BigDecimal.ZERO) == 0) {
                log.warn("Cannot extend {} - failed to get price", symbol);
                return false;
            }

            // Calculate extension size
            BigDecimal extensionSize = position.getSizeUsdt()
                    .multiply(BigDecimal.valueOf(scalePercent))
                    .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP);

            // Check if we have enough capital
            BigDecimal availableCash = accountingService.getCashBalance();
            if (extensionSize.compareTo(availableCash) > 0) {
                log.warn("Cannot extend {} - insufficient capital", symbol);
                return false;
            }

            // TODO: Implement actual position extension in PositionService
            log.info("Extending {} by {}% ({} USDT) @ {} - Reason: {}",
                    symbol, scalePercent, extensionSize, currentPrice, reason);

            return true;

        } catch (Exception e) {
            log.error("Failed to extend position {}: {}", symbol, e.getMessage());
            return false;
        }
    }

    private boolean reducePosition(String symbol, int scalePercent, String reason, TraderState state) {
        try {
            PositionDTO position = positionService.getPositionBySymbol(symbol);
            if (position == null) {
                log.warn("Cannot reduce {} - position not found", symbol);
                return false;
            }

            BigDecimal currentPrice = binanceClient.getPrice(symbol);
            if (currentPrice.compareTo(BigDecimal.ZERO) == 0) {
                log.warn("Cannot reduce {} - failed to get price", symbol);
                return false;
            }

            // Calculate reduction size
            BigDecimal reductionSize = position.getSizeUsdt()
                    .multiply(BigDecimal.valueOf(scalePercent))
                    .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP);

            // Calculate partial PnL
            BigDecimal partialPnL = calculatePnL(position, currentPrice)
                    .multiply(BigDecimal.valueOf(scalePercent))
                    .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP);

            // TODO: Implement actual position reduction in PositionService
            log.info("Reducing {} by {}% ({} USDT) @ {} - PnL: {} - Reason: {}",
                    symbol, scalePercent, reductionSize, currentPrice, partialPnL, reason);

            return true;

        } catch (Exception e) {
            log.error("Failed to reduce position {}: {}", symbol, e.getMessage());
            return false;
        }
    }

    private OpenedPositionInfo openNewPosition(NewOpportunity opportunity, TraderState state) {
        try {
            String symbol = opportunity.getSymbol();
            if (!symbol.endsWith("USDT")) {
                symbol = symbol + "USDT";
            }

            // Check if we already have this position
            if (positionService.getPositionBySymbol(symbol) != null) {
                log.warn("Already have position in {}, skipping", symbol);
                return null;
            }

            BigDecimal price = binanceClient.getPrice(symbol);
            if (price.compareTo(BigDecimal.ZERO) == 0) {
                log.warn("Failed to get price for {}, skipping", symbol);
                return null;
            }

            // Get available cash from accounting ledger
            BigDecimal availableCash = accountingService.getCashBalance();

            // Calculate position size based on conviction
            BigDecimal baseSizePercent = positionSizePercent;
            if (opportunity.getConviction() >= 80) {
                baseSizePercent = baseSizePercent.multiply(BigDecimal.valueOf(1.5)); // 50% larger for high conviction
            }

            BigDecimal sizeUsdt = availableCash
                    .multiply(baseSizePercent)
                    .setScale(2, RoundingMode.HALF_UP);

            if (sizeUsdt.compareTo(availableCash) > 0) {
                log.warn("Insufficient capital for {}", symbol);
                return null;
            }

            // Minimum position size check
            if (sizeUsdt.compareTo(BigDecimal.valueOf(10)) < 0) {
                log.warn("Position size too small for {}: {} USDT", symbol, sizeUsdt);
                return null;
            }

            String direction = opportunity.getDirection().name();

            // Open position via paper trading
            BinanceClient.TradeResult result = binanceClient.openPosition(
                    symbol,
                    direction,
                    sizeUsdt,
                    opportunity.getLeverage()
            );

            if (result.isSuccess()) {
                // Create position in DB
                Position position = positionService.createPosition(
                        symbol,
                        direction,
                        result.getPrice(),
                        result.getQuantity(),
                        sizeUsdt,
                        opportunity.getLeverage(),
                        opportunity.getConviction(),
                        opportunity.getReason()
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

                log.info("Opened {} {} @ {} (conviction: {}, leverage: {}x, size: {} USDT)",
                        direction, symbol, result.getPrice(),
                        opportunity.getConviction(), opportunity.getLeverage(), sizeUsdt);
                
                return OpenedPositionInfo.builder()
                        .symbol(symbol)
                        .direction(direction)
                        .entryPrice(result.getPrice())
                        .sizeUsdt(sizeUsdt)
                        .leverage(opportunity.getLeverage())
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
            BigDecimal currentPrice = binanceClient.getPrice(p.getSymbol());
            BigDecimal pnl = calculatePnL(p, currentPrice);
            BigDecimal pnlPercent = p.getSizeUsdt().compareTo(BigDecimal.ZERO) > 0
                    ? pnl.divide(p.getSizeUsdt(), 4, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                    : BigDecimal.ZERO;

            Duration holdTime = Duration.between(p.getEntryTime(), Instant.now());
            String holdTimeStr = formatDuration(holdTime);

            // Risk assessment
            String riskLevel = assessRisk(pnlPercent, holdTime);

            sb.append(String.format("- %s: %s @ %s → %s (PnL: %s%%, Haltezeit: %s, Leverage: %dx) %s\n",
                    p.getSymbol(),
                    p.getDirection(),
                    p.getEntryPrice(),
                    currentPrice,
                    pnlPercent.setScale(2, RoundingMode.HALF_UP),
                    holdTimeStr,
                    p.getLeverage(),
                    riskLevel));
        }

        return sb.toString();
    }

    private String assessRisk(BigDecimal pnlPercent, Duration holdTime) {
        if (pnlPercent.compareTo(BigDecimal.valueOf(-25)) < 0) {
            return "🔴 DANGER: Critical loss";
        } else if (pnlPercent.compareTo(BigDecimal.valueOf(-15)) < 0) {
            return "🟡 WARNING: Heavy loss";
        } else if (holdTime.toHours() > 48) {
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
     */
    private String buildDeploymentInfo(TraderState state, List<PositionDTO> positions) {
        BigDecimal positionsValue = positions.stream()
                .map(PositionDTO::getSizeUsdt)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal totalEquity = state.getCurrentCapital().add(positionsValue);
        BigDecimal deploymentRatio = totalEquity.compareTo(BigDecimal.ZERO) > 0
                ? positionsValue.divide(totalEquity, 4, RoundingMode.HALF_UP)
                : BigDecimal.ZERO;

        String status;
        if (deploymentRatio.compareTo(minDeploymentRatio) < 0) {
            status = "⚠️ UNTER ZIEL - Mehr Positionen eröffnen!";
        } else if (deploymentRatio.compareTo(maxDeploymentRatio) > 0) {
            status = "⚠️ ÜBER LIMIT - Keine neuen Positionen!";
        } else {
            status = "✅ Im Zielbereich";
        }

        return String.format("DEPLOYMENT: %.1f%% (Ziel: %.0f%%-%.0f%%) %s\nVerfügbares Kapital: %s USDT\nOffene Slots: %d/%d",
                deploymentRatio.multiply(BigDecimal.valueOf(100)),
                minDeploymentRatio.multiply(BigDecimal.valueOf(100)),
                maxDeploymentRatio.multiply(BigDecimal.valueOf(100)),
                status,
                state.getCurrentCapital(),
                maxPositions - positions.size(),
                maxPositions);
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

    public int getMaxPositions() {
        return maxPositions;
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
        private String error;
        private String marketSummary;
        private int openPositionsBefore;
        private int positionsClosed;
        private int positionsOpened;
        private int coinsAnalyzed;
        private BigDecimal availableCapital;

        public static CycleResult skipped(String reason) {
            return CycleResult.builder()
                    .skipped(true)
                    .error(reason)
                    .build();
        }
    }
}

