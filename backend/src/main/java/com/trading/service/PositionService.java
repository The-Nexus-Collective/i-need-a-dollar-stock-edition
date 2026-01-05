package com.trading.service;

import com.trading.dto.PositionDTO;
import com.trading.dto.EquityData;
import com.trading.entity.Position;
import com.trading.entity.Trade;
import com.trading.entity.TraderState;
import com.trading.repository.PositionRepository;
import com.trading.repository.TradeRepository;
import com.trading.repository.TraderStateRepository;
import com.trading.integration.binance.BinanceClient;
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
    private final BinanceClient binanceClient;
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
                        price = binanceClient.getPrice(p.getSymbol());
                    }
                    return toDTO(p, price);
                });
    }

    /**
     * Get open position by symbol
     */
    public Optional<PositionDTO> getOpenPositionBySymbol(String symbol) {
        return positionRepository.findOpenPositionBySymbol(symbol)
                .map(p -> toDTO(p, binanceClient.getPrice(p.getSymbol())));
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
                    .map(p -> toDTO(p, binanceClient.getPrice(p.getSymbol())))
                    .orElse(null);
        }
    }

    /**
     * Create a new position and return the entity (for use with AccountingService)
     */
    @Transactional
    public Position createPosition(String symbol, String direction, BigDecimal entryPrice,
                                       BigDecimal quantity, BigDecimal sizeUsdt, int leverage,
                                       int conviction, String reasoning) {
        Position position = Position.builder()
                .id(UUID.randomUUID().toString().replace("-", ""))
                .symbol(symbol)
                .direction(direction.toUpperCase())
                .entryPrice(entryPrice)
                .quantity(quantity)
                .sizeUsdt(sizeUsdt)
                .leverage(leverage)
                .conviction(BigDecimal.valueOf(conviction))
                .reasoning(reasoning)
                .status("OPEN")
                .entryTime(Instant.now())
                .build();
        
        position = positionRepository.save(position);
        log.info("Created position: {} {} {}", position.getId(), symbol, direction);
        
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
        
        position.setStatus(reason != null ? reason : "CLOSED");
        position.setExitTime(exitTime);
        position.setExitPrice(exitPrice);
        position.setRealizedPnl(pnl);
        
        position = positionRepository.save(position);
        
        // Record in accounting ledger (double-entry bookkeeping)
        accountingService.recordClosePosition(
                positionId,
                position.getSymbol(),
                position.getSizeUsdt(),
                pnl,
                exitFee,
                exitPrice,
                reason != null ? reason : "CLOSED"
        );
        
        // Create trade record for history
        BigDecimal pnlPercent = position.getSizeUsdt().compareTo(BigDecimal.ZERO) > 0
                ? pnl.divide(position.getSizeUsdt(), 4, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                : BigDecimal.ZERO;
        
        Trade trade = Trade.builder()
                .id(UUID.randomUUID().toString().replace("-", ""))
                .positionId(positionId)
                .symbol(position.getSymbol())
                .direction(position.getDirection())
                .entryPrice(position.getEntryPrice())
                .exitPrice(exitPrice)
                .quantity(position.getQuantity())
                .sizeUsdt(position.getSizeUsdt())
                .leverage(position.getLeverage())
                .pnlUsdt(pnl)
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
     * Close a position due to margin call (forced liquidation).
     * Uses MARGIN_CALL accounting and records the full loss.
     */
    @Transactional
    public PositionDTO closePositionMarginCall(String positionId, BigDecimal exitPrice) {
        Position position = positionRepository.findById(positionId)
                .orElseThrow(() -> new RuntimeException("Position not found: " + positionId));
        
        // Calculate PnL at the exit price (should be near -100% of margin)
        BigDecimal pnl = position.calculateUnrealizedPnl(exitPrice);
        Instant exitTime = Instant.now();
        long durationSeconds = java.time.Duration.between(position.getEntryTime(), exitTime).getSeconds();
        
        // Set status to MARGIN_CALL (distinct from CLOSED)
        position.setStatus("MARGIN_CALL");
        position.setExitTime(exitTime);
        position.setExitPrice(exitPrice);
        position.setRealizedPnl(pnl);
        
        position = positionRepository.save(position);
        
        // Record in accounting ledger using MARGIN_CALL transaction type
        accountingService.recordMarginCall(
                positionId,
                position.getSymbol(),
                position.getSizeUsdt(),
                pnl,
                exitPrice
        );
        
        // Create trade record for history with MARGIN_CALL exit reason
        BigDecimal pnlPercent = position.getSizeUsdt().compareTo(BigDecimal.ZERO) > 0
                ? pnl.divide(position.getSizeUsdt(), 4, RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                : BigDecimal.ZERO;
        
        Trade trade = Trade.builder()
                .id(UUID.randomUUID().toString().replace("-", ""))
                .positionId(positionId)
                .symbol(position.getSymbol())
                .direction(position.getDirection())
                .entryPrice(position.getEntryPrice())
                .exitPrice(exitPrice)
                .quantity(position.getQuantity())
                .sizeUsdt(position.getSizeUsdt())
                .leverage(position.getLeverage())
                .pnlUsdt(pnl)
                .pnlPercent(pnlPercent)
                .entryTime(position.getEntryTime())
                .exitTime(exitTime)
                .durationSeconds((int) durationSeconds)
                .exitReason("MARGIN_CALL")
                .conviction(position.getConviction())
                .reasoning(position.getReasoning())
                .totalFees(BigDecimal.ZERO) // No fees on margin call
                .build();
        
        tradeRepository.save(trade);
        
        // Update trader state statistics (always a loss for margin call)
        updateTraderStateStats(false);
        
        log.error("MARGIN CALL: Closed position {} {} {} with PnL: {} ({}%)", 
                positionId, position.getSymbol(), position.getDirection(), pnl, pnlPercent);
        
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
                            .sizeUsdt(p.getSizeUsdt())
                            .unrealizedPnl(pnl)
                            .pnlPercent(pnlPct)
                            .build();
                })
                .collect(Collectors.toList());
        
        for (Position p : positions) {
            positionsEntryCost = positionsEntryCost.add(p.getSizeUsdt());
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
                        binanceClient::getPrice,
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
        
        // Calculate liquidation price
        BigDecimal liquidationPrice = null;
        if ("OPEN".equals(p.getStatus()) && p.getLeverage() != null && p.getLeverage() > 0) {
            BigDecimal leverageFactor = BigDecimal.ONE.divide(
                    BigDecimal.valueOf(p.getLeverage()), 8, RoundingMode.HALF_UP);
            
            if ("LONG".equalsIgnoreCase(p.getDirection())) {
                // LONG: liquidation when price drops by margin percentage
                liquidationPrice = p.getEntryPrice().multiply(BigDecimal.ONE.subtract(leverageFactor))
                        .setScale(8, RoundingMode.HALF_UP);
            } else {
                // SHORT: liquidation when price rises by margin percentage
                liquidationPrice = p.getEntryPrice().multiply(BigDecimal.ONE.add(leverageFactor))
                        .setScale(8, RoundingMode.HALF_UP);
            }
        }
        
        return PositionDTO.builder()
                .id(p.getId())
                .symbol(p.getSymbol())
                .direction(p.getDirection())
                .entryPrice(p.getEntryPrice())
                .quantity(p.getQuantity())
                .sizeUsdt(p.getSizeUsdt())
                .leverage(p.getLeverage())
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
                .liquidationPrice(liquidationPrice)
                .build();
    }
}

