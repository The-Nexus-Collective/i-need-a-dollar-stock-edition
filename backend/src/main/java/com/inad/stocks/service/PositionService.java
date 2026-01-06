package com.inad.stocks.service;

import com.inad.stocks.dto.PositionDTO;
import com.inad.stocks.dto.EquityData;
import com.inad.stocks.entity.Position;
import com.inad.stocks.entity.Trade;
import com.inad.stocks.entity.TraderState;
import com.inad.stocks.repository.PositionRepository;
import com.inad.stocks.repository.TradeRepository;
import com.inad.stocks.repository.TraderStateRepository;
import com.inad.stocks.integration.broker.StockBrokerClient;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Service for position management
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PositionService {

    private final PositionRepository positionRepository;
    private final TradeRepository tradeRepository;
    private final TraderStateRepository traderStateRepository;
    private final StockBrokerClient stockBrokerClient;
    private final AccountingService accountingService;

    /**
     * Get all open positions enriched with live prices
     */
    public List<PositionDTO> getOpenPositions() {
        List<Position> positions = positionRepository.findOpenPositions();
        Map<String, BigDecimal> livePrices = getLivePrices(positions);
        
        return positions.stream()
                .map(p -> toDTO(p, livePrices.get(p.getSymbol())))
                .collect(Collectors.toList());
    }

    /**
     * Get closed positions
     */
    public List<PositionDTO> getClosedPositions(int limit) {
        return positionRepository.findClosedPositions().stream()
                .limit(limit)
                .map(p -> toDTO(p, null))
                .collect(Collectors.toList());
    }

    /**
     * Get position by ID
     */
    public Optional<PositionDTO> getPositionById(String id) {
        return positionRepository.findById(id)
                .map(p -> {
                    BigDecimal price = null;
                    if ("OPEN".equals(p.getStatus())) {
                        price = stockBrokerClient.getPrice(p.getSymbol());
                    }
                    return toDTO(p, price);
                });
    }

    /**
     * Get open position by symbol
     */
    public Optional<PositionDTO> getOpenPositionBySymbol(String symbol) {
        return positionRepository.findOpenPositionBySymbol(symbol)
                .map(p -> toDTO(p, stockBrokerClient.getPrice(p.getSymbol())));
    }

    /**
     * Get open position by symbol (returns null if not found).
     * If multiple positions exist for the same symbol, returns the most recent one.
     */
    public PositionDTO getPositionBySymbol(String symbol) {
        try {
            return getOpenPositionBySymbol(symbol).orElse(null);
        } catch (Exception e) {
            // If multiple results found, get the first one (most recent)
            log.warn("Multiple open positions found for {}, using most recent", symbol);
            List<Position> positions = positionRepository.findBySymbolOrderByEntryTimeDesc(symbol);
            return positions.stream()
                    .filter(p -> "OPEN".equals(p.getStatus()))
                    .findFirst()
                    .map(p -> toDTO(p, stockBrokerClient.getPrice(p.getSymbol())))
                    .orElse(null);
        }
    }

    /**
     * Create a new position and return the entity (for use with AccountingService)
     */
    @Transactional
    public Position createPosition(String symbol, String direction, BigDecimal entryPrice,
                                       BigDecimal quantity, BigDecimal sizeUsdt,
                                       int conviction, String reasoning) {
        return createPosition(symbol, direction, entryPrice, quantity, sizeUsdt,
                conviction, reasoning, null, null, null, null, null, null, null);
    }
    
    /**
     * Create a new position with Pre-Mortem data for self-learning.
     */
    @Transactional
    public Position createPosition(String symbol, String direction, BigDecimal entryPrice,
                                   BigDecimal quantity, BigDecimal sizeUsdt,
                                   int conviction, String reasoning,
                                   String preMortem, String bullCase, String bearCase,
                                   Integer expectedHoldHoursMin, Integer expectedHoldHoursMax,
                                   BigDecimal targetPnlPercent, BigDecimal maxAcceptableLossPercent) {
        Position position = Position.builder()
                .id(UUID.randomUUID().toString().replace("-", ""))
                .symbol(symbol)
                .direction(direction.toUpperCase())
                .entryPrice(entryPrice)
                .quantity(quantity)
                .sizeUsd(sizeUsdt)
                .conviction(BigDecimal.valueOf(conviction))
                .reasoning(reasoning)
                .status("OPEN")
                .entryTime(Instant.now())
                // Self-learning Pre-Mortem fields
                .preMortem(preMortem)
                .bullCase(bullCase)
                .bearCase(bearCase)
                .expectedHoldHoursMin(expectedHoldHoursMin)
                .expectedHoldHoursMax(expectedHoldHoursMax)
                .targetPnlPercent(targetPnlPercent)
                .maxAcceptableLossPercent(maxAcceptableLossPercent)
                .build();
        
        position = positionRepository.save(position);
        log.info("Created position: {} {} {}, preMortem={}", 
                position.getId(), symbol, direction, preMortem != null ? "yes" : "no");
        
        return position;
    }

    /**
     * Close a position with accounting
     */
    @Transactional
    public PositionDTO closePosition(String positionId, BigDecimal exitPrice, String reason) {
        return closePosition(positionId, exitPrice, reason, BigDecimal.ZERO);
    }

    /**
     * Close a position with exit fee
     */
    @Transactional
    public PositionDTO closePosition(String positionId, BigDecimal exitPrice, String reason, BigDecimal exitFee) {
        Position position = positionRepository.findById(positionId)
                .orElseThrow(() -> new RuntimeException("Position not found: " + positionId));
        
        BigDecimal pnl = position.calculateUnrealizedPnl(exitPrice);
        Instant exitTime = Instant.now();
        long durationSeconds = java.time.Duration.between(position.getEntryTime(), exitTime).getSeconds();
        
        position.setStatus("CLOSED");
        position.setExitTime(exitTime);
        position.setExitPrice(exitPrice);
        position.setRealizedPnl(pnl);
        
        position = positionRepository.save(position);
        
        // Record in accounting ledger (double-entry bookkeeping)
        accountingService.recordClosePosition(
                positionId,
                position.getSymbol(),
                position.getSizeUsd(),
                pnl,
                exitFee,
                exitPrice,
                "CLOSED"
        );
        
        // Create trade record for history
        BigDecimal pnlPercent = position.getSizeUsd().compareTo(BigDecimal.ZERO) > 0
                ? pnl.divide(position.getSizeUsd(), 4, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                : BigDecimal.ZERO;
        
        Trade trade = Trade.builder()
                .id(UUID.randomUUID().toString().replace("-", ""))
                .positionId(positionId)
                .symbol(position.getSymbol())
                .direction(position.getDirection())
                .entryPrice(position.getEntryPrice())
                .exitPrice(exitPrice)
                .quantity(position.getQuantity())
                .sizeUsd(position.getSizeUsd())
                .pnlUsd(pnl)
                .pnlPercent(pnlPercent)
                .entryTime(position.getEntryTime())
                .exitTime(exitTime)
                .durationSeconds((int) durationSeconds)
                .exitReason(reason != null ? reason : "CLOSED")
                .conviction(position.getConviction())
                .reasoning(position.getReasoning())
                .totalFees(exitFee)
                .build();
        
        tradeRepository.save(trade);
        log.info("Recorded trade: {} {} PnL: {}", position.getSymbol(), position.getDirection(), pnl);
        
        // Update trader state for statistics only (capital is tracked via accounting ledger)
        updateTraderStateStats(pnl.compareTo(BigDecimal.ZERO) > 0);
        
        log.info("Closed position: {} with PnL: {}", positionId, pnl);
        
        return toDTO(position, exitPrice);
    }
    
    /**
     * Update trader state statistics after closing a position.
     * Note: Capital tracking is now handled by AccountingService.
     */
    private void updateTraderStateStats(boolean isWinner) {
        TraderState state = traderStateRepository.getOrCreateMain();
        state.setTotalTrades(state.getTotalTrades() + 1);
        if (isWinner) {
            state.setWinningTrades(state.getWinningTrades() + 1);
        } else {
            state.setLosingTrades(state.getLosingTrades() + 1);
        }
        traderStateRepository.save(state);
    }

    /**
     * Extend (add to) an existing position.
     * 
     * This executes an additional trade in the same direction and updates
     * the position with a weighted average entry price.
     * 
     * @param positionId The position to extend
     * @param addedSizeUsdt Amount to add in USDT
     * @param reason Reason for extending
     * @return Result containing trade details and updated position info
     */
    @Transactional
    public ExtendResult extendPosition(String positionId, BigDecimal addedSizeUsdt, String reason) {
        Position position = positionRepository.findById(positionId)
                .orElseThrow(() -> new RuntimeException("Position not found: " + positionId));
        
        if (!"OPEN".equals(position.getStatus())) {
            throw new IllegalStateException("Cannot extend closed position");
        }
        
        // Execute trade via broker (same direction)
        StockBrokerClient.TradeResult tradeResult = stockBrokerClient.openPosition(
                position.getSymbol(),
                position.getDirection(),
                addedSizeUsdt
        );
        
        if (!tradeResult.isSuccess()) {
            throw new RuntimeException("Failed to extend position: " + tradeResult.getError());
        }
        
        // Broker returns whole shares only - calculate weighted average entry price
        BigDecimal addedQuantity = tradeResult.getQuantity().setScale(0, RoundingMode.DOWN); // Ensure whole shares
        BigDecimal oldTotalValue = position.getEntryPrice().multiply(position.getQuantity());
        BigDecimal newTotalValue = tradeResult.getPrice().multiply(addedQuantity);
        BigDecimal newTotalQuantity = position.getQuantity().add(addedQuantity);
        BigDecimal newAvgEntryPrice = oldTotalValue.add(newTotalValue)
                .divide(newTotalQuantity, 8, RoundingMode.HALF_UP);
        
        // Update position
        position.setEntryPrice(newAvgEntryPrice);
        position.setQuantity(newTotalQuantity);
        position.setSizeUsd(position.getSizeUsd().add(addedSizeUsdt));
        
        position = positionRepository.save(position);
        
        // Record in accounting ledger
        accountingService.recordExtendPosition(
                positionId,
                position.getSymbol(),
                addedSizeUsdt,
                tradeResult.getFee(),
                tradeResult.getSpread(),
                tradeResult.getSlippage(),
                tradeResult.getPrice(),
                position.getDirection()
        );
        
        log.info("Extended position {} {}: +{} whole shares ({} USDT) @ {} (new avg: {}, total: {} shares, {} USDT)",
                position.getSymbol(), position.getDirection(),
                addedQuantity.intValue(), addedSizeUsdt, tradeResult.getPrice(), 
                newAvgEntryPrice, newTotalQuantity.intValue(), position.getSizeUsd());
        
        return ExtendResult.builder()
                .success(true)
                .symbol(position.getSymbol())
                .addedSize(addedSizeUsdt)
                .price(tradeResult.getPrice())
                .newAvgEntryPrice(newAvgEntryPrice)
                .newTotalSize(position.getSizeUsd())
                .fee(tradeResult.getFee())
                .build();
    }

    /**
     * Reduce (partially close) an existing position.
     * 
     * This executes a partial close and realizes proportional PnL.
     * 
     * @param positionId The position to reduce
     * @param scalePercent Percentage of position to close (1-99)
     * @param reason Reason for reducing
     * @return Result containing trade details and partial PnL
     */
    @Transactional
    public ReduceResult reducePosition(String positionId, int scalePercent, String reason) {
        Position position = positionRepository.findById(positionId)
                .orElseThrow(() -> new RuntimeException("Position not found: " + positionId));
        
        if (!"OPEN".equals(position.getStatus())) {
            throw new IllegalStateException("Cannot reduce closed position");
        }
        
        if (scalePercent < 1 || scalePercent > 99) {
            throw new IllegalArgumentException("Scale percent must be between 1 and 99");
        }
        
        // Calculate reduction amounts - WHOLE SHARES ONLY
        BigDecimal reductionFactor = BigDecimal.valueOf(scalePercent).divide(BigDecimal.valueOf(100), 8, RoundingMode.HALF_UP);
        BigDecimal reducedQuantity = position.getQuantity().multiply(reductionFactor).setScale(0, RoundingMode.DOWN);
        
        // Must reduce at least 1 whole share
        if (reducedQuantity.compareTo(BigDecimal.ONE) < 0) {
            throw new IllegalArgumentException(
                    "Cannot reduce position: " + scalePercent + "% of " + position.getQuantity() + 
                    " shares = " + position.getQuantity().multiply(reductionFactor).setScale(2, RoundingMode.HALF_UP) + 
                    " shares, but minimum is 1 whole share");
        }
        
        // Calculate actual USD reduction based on whole shares
        BigDecimal actualReductionFactor = reducedQuantity.divide(position.getQuantity(), 8, RoundingMode.HALF_UP);
        BigDecimal reducedSizeUsdt = position.getSizeUsd().multiply(actualReductionFactor).setScale(2, RoundingMode.HALF_UP);
        
        // Get current price
        BigDecimal currentPrice = stockBrokerClient.getPrice(position.getSymbol());
        if (currentPrice.compareTo(BigDecimal.ZERO) == 0) {
            throw new RuntimeException("Failed to get price for " + position.getSymbol());
        }
        
        // Execute partial close via Binance
        String closeSide = "LONG".equals(position.getDirection()) ? "SELL" : "BUY";
        StockBrokerClient.TradeResult tradeResult = stockBrokerClient.closePosition(
                position.getSymbol(),
                closeSide,
                reducedQuantity,
                position.getEntryPrice()
        );
        
        if (!tradeResult.isSuccess()) {
            throw new RuntimeException("Failed to reduce position: " + tradeResult.getError());
        }
        
        // Calculate partial PnL
        BigDecimal totalUnrealizedPnl = position.calculateUnrealizedPnl(tradeResult.getPrice());
        BigDecimal partialPnl = totalUnrealizedPnl.multiply(reductionFactor).setScale(8, RoundingMode.HALF_UP);
        
        // Update position (reduce size, keep entry price)
        position.setQuantity(position.getQuantity().subtract(reducedQuantity));
        position.setSizeUsd(position.getSizeUsd().subtract(reducedSizeUsdt));
        
        position = positionRepository.save(position);
        
        // Record in accounting ledger
        accountingService.recordReducePosition(
                positionId,
                position.getSymbol(),
                reducedSizeUsdt,
                partialPnl,
                tradeResult.getFee(),
                tradeResult.getPrice(),
                scalePercent
        );
        
        // Create partial trade record for history
        BigDecimal pnlPercent = reducedSizeUsdt.compareTo(BigDecimal.ZERO) > 0
                ? partialPnl.divide(reducedSizeUsdt, 4, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                : BigDecimal.ZERO;
        
        Trade trade = Trade.builder()
                .id(UUID.randomUUID().toString().replace("-", ""))
                .positionId(positionId)
                .symbol(position.getSymbol())
                .direction(position.getDirection())
                .entryPrice(position.getEntryPrice())
                .exitPrice(tradeResult.getPrice())
                .quantity(reducedQuantity)
                .sizeUsd(reducedSizeUsdt)
                .pnlUsd(partialPnl)
                .pnlPercent(pnlPercent)
                .entryTime(position.getEntryTime())
                .exitTime(Instant.now())
                .durationSeconds(0) // Partial close
                .exitReason("PARTIAL_CLOSE_" + scalePercent + "%: " + reason)
                .conviction(position.getConviction())
                .reasoning(position.getReasoning())
                .totalFees(tradeResult.getFee())
                .build();
        
        tradeRepository.save(trade);
        
        log.info("Reduced position {} {}: -{} whole shares ({}%, {} USDT) @ {} - PnL: {} (remaining: {} shares, {} USDT)",
                position.getSymbol(), position.getDirection(),
                reducedQuantity.intValue(), scalePercent, reducedSizeUsdt, 
                tradeResult.getPrice(), partialPnl, position.getQuantity().intValue(), position.getSizeUsd());
        
        return ReduceResult.builder()
                .success(true)
                .symbol(position.getSymbol())
                .reducedSize(reducedSizeUsdt)
                .scalePercent(scalePercent)
                .price(tradeResult.getPrice())
                .partialPnl(partialPnl)
                .remainingSize(position.getSizeUsd())
                .fee(tradeResult.getFee())
                .build();
    }

    /**
     * Result of extending a position.
     */
    @lombok.Data
    @lombok.Builder
    public static class ExtendResult {
        private boolean success;
        private String symbol;
        private BigDecimal addedSize;
        private BigDecimal price;
        private BigDecimal newAvgEntryPrice;
        private BigDecimal newTotalSize;
        private BigDecimal fee;
        private String error;
    }

    /**
     * Result of reducing a position.
     */
    @lombok.Data
    @lombok.Builder
    public static class ReduceResult {
        private boolean success;
        private String symbol;
        private BigDecimal reducedSize;
        private int scalePercent;
        private BigDecimal price;
        private BigDecimal partialPnl;
        private BigDecimal remainingSize;
        private BigDecimal fee;
        private String error;
    }

    /**
     * Calculate current equity data for WebSocket.
     * Now uses AccountingService for authoritative cash balance.
     */
    public EquityData calculateEquityData() {
        List<Position> positions = positionRepository.findOpenPositions();
        Map<String, BigDecimal> livePrices = getLivePrices(positions);
        
        // Get cash balance from accounting ledger (single source of truth)
        BigDecimal cash = accountingService.getCashBalance();
        
        BigDecimal positionsEntryCost = BigDecimal.ZERO;
        BigDecimal unrealizedPnl = BigDecimal.ZERO;
        
        List<EquityData.PositionDetail> details = positions.stream()
                .map(p -> {
                    BigDecimal price = livePrices.getOrDefault(p.getSymbol(), p.getEntryPrice());
                    BigDecimal pnl = p.calculateUnrealizedPnl(price);
                    BigDecimal pnlPct = p.calculatePnlPercent(price);
                    
                    return EquityData.PositionDetail.builder()
                            .symbol(p.getSymbol())
                            .direction(p.getDirection())
                            .entryPrice(p.getEntryPrice())
                            .currentPrice(price)
                            .sizeUsd(p.getSizeUsd())
                            .unrealizedPnl(pnl)
                            .pnlPercent(pnlPct)
                            .build();
                })
                .collect(Collectors.toList());
        
        for (Position p : positions) {
            positionsEntryCost = positionsEntryCost.add(p.getSizeUsd());
            BigDecimal price = livePrices.getOrDefault(p.getSymbol(), p.getEntryPrice());
            unrealizedPnl = unrealizedPnl.add(p.calculateUnrealizedPnl(price));
        }
        
        // Positions current value = entry cost + unrealized PnL
        BigDecimal positionsCurrentValue = positionsEntryCost.add(unrealizedPnl);
        
        // Total equity = cash + current market value of positions
        BigDecimal totalEquity = cash.add(positionsCurrentValue);
        
        return EquityData.builder()
                .timestamp(Instant.now().toString())
                .totalEquity(totalEquity)
                .cash(cash)
                .positionsValue(positionsEntryCost)
                .unrealizedPnl(unrealizedPnl)
                .positionDetails(details)
                .build();
    }

    /**
     * Count open positions
     */
    public int countOpenPositions() {
        return positionRepository.countOpenPositions();
    }

    private Map<String, BigDecimal> getLivePrices(List<Position> positions) {
        return positions.stream()
                .map(Position::getSymbol)
                .distinct()
                .collect(Collectors.toMap(
                        symbol -> symbol,
                        stockBrokerClient::getPrice,
                        (a, b) -> a
                ));
    }

    private PositionDTO toDTO(Position p, BigDecimal currentPrice) {
        BigDecimal unrealizedPnl = null;
        BigDecimal pnlPercent = null;
        
        if (currentPrice != null && "OPEN".equals(p.getStatus())) {
            unrealizedPnl = p.calculateUnrealizedPnl(currentPrice);
            pnlPercent = p.calculatePnlPercent(currentPrice);
        }
        
        return PositionDTO.builder()
                .id(p.getId())
                .symbol(p.getSymbol())
                .direction(p.getDirection())
                .entryPrice(p.getEntryPrice())
                .quantity(p.getQuantity())
                .sizeUsd(p.getSizeUsd())
                .stopLossPrice(p.getStopLossPrice())
                .takeProfitPrice(p.getTakeProfitPrice())
                .status(p.getStatus())
                .entryTime(p.getEntryTime())
                .exitTime(p.getExitTime())
                .exitPrice(p.getExitPrice())
                .realizedPnl(p.getRealizedPnl())
                .unrealizedPnl(unrealizedPnl)
                .pnlPercent(pnlPercent)
                .conviction(p.getConviction())
                .reasoning(p.getReasoning())
                .currentPrice(currentPrice)
                // Pre-Mortem / Self-Learning fields
                .preMortem(p.getPreMortem())
                .bullCase(p.getBullCase())
                .bearCase(p.getBearCase())
                .expectedHoldHoursMin(p.getExpectedHoldHoursMin())
                .expectedHoldHoursMax(p.getExpectedHoldHoursMax())
                .targetPnlPercent(p.getTargetPnlPercent())
                .maxAcceptableLossPercent(p.getMaxAcceptableLossPercent())
                .build();
    }
}

