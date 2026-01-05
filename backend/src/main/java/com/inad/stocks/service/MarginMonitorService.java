package com.inad.stocks.service;

import com.inad.stocks.dto.PositionDTO;
import com.inad.stocks.entity.Position;
import com.inad.stocks.integration.broker.StockBrokerClient;
import com.inad.stocks.repository.PositionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * Service for monitoring margin positions and executing margin calls.
 * 
 * Checks all open positions every second (called from EquityWebSocketHandler)
 * and triggers margin calls when positions hit their liquidation price.
 * 
 * Liquidation Price Formula:
 * - LONG: liquidationPrice = entryPrice * (1 - 1/leverage)
 * - SHORT: liquidationPrice = entryPrice * (1 + 1/leverage)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MarginMonitorService {

    private final PositionRepository positionRepository;
    private final PositionService positionService;
    private final StockBrokerClient stockBrokerClient;

    @Value("${trading.margin.enabled:true}")
    private boolean marginMonitoringEnabled;

    @Value("${trading.margin.warning-threshold:5.0}")
    private BigDecimal warningThreshold;

    @Value("${trading.margin.critical-threshold:2.0}")
    private BigDecimal criticalThreshold;

    // Track which positions have already been warned to avoid spam
    private final Set<String> warnedPositions = ConcurrentHashMap.newKeySet();
    private final Set<String> criticalWarnedPositions = ConcurrentHashMap.newKeySet();

    /**
     * Result of a margin check operation
     */
    @lombok.Data
    @lombok.Builder
    public static class MarginCheckResult {
        private int positionsChecked;
        private int positionsWarning;
        private int positionsCritical;
        private int marginCallsExecuted;
        private List<MarginCallInfo> marginCalls;
    }

    /**
     * Info about an executed margin call
     */
    @lombok.Data
    @lombok.Builder
    public static class MarginCallInfo {
        private String positionId;
        private String symbol;
        private String direction;
        private BigDecimal entryPrice;
        private BigDecimal exitPrice;
        private BigDecimal liquidationPrice;
        private BigDecimal lossAmount;
        private Instant executedAt;
    }

    /**
     * Check all open positions for margin violations.
     * Called every second from EquityWebSocketHandler.
     * 
     * @return MarginCheckResult with details of any actions taken
     */
    public MarginCheckResult checkAllPositions() {
        if (!marginMonitoringEnabled) {
            return MarginCheckResult.builder()
                    .positionsChecked(0)
                    .build();
        }

        List<Position> openPositions = positionRepository.findOpenPositions();
        if (openPositions.isEmpty()) {
            return MarginCheckResult.builder()
                    .positionsChecked(0)
                    .build();
        }

        // Get live prices for all positions
        Map<String, BigDecimal> livePrices = getLivePrices(openPositions);

        int warningCount = 0;
        int criticalCount = 0;
        int marginCallsExecuted = 0;
        java.util.List<MarginCallInfo> marginCalls = new java.util.ArrayList<>();

        for (Position position : openPositions) {
            BigDecimal currentPrice = livePrices.get(position.getSymbol());
            if (currentPrice == null || currentPrice.compareTo(BigDecimal.ZERO) == 0) {
                continue;
            }

            BigDecimal liquidationPrice = calculateLiquidationPrice(position);
            BigDecimal distanceToLiq = calculateDistanceToLiquidation(position, currentPrice, liquidationPrice);

            // Check if position should be liquidated
            if (shouldLiquidate(position, currentPrice, liquidationPrice)) {
                MarginCallInfo marginCall = executeMarginCall(position, currentPrice, liquidationPrice);
                if (marginCall != null) {
                    marginCalls.add(marginCall);
                    marginCallsExecuted++;
                    
                    // Remove from warned sets
                    warnedPositions.remove(position.getId());
                    criticalWarnedPositions.remove(position.getId());
                }
                continue;
            }

            // Check for warning thresholds
            if (distanceToLiq.compareTo(criticalThreshold) < 0) {
                criticalCount++;
                if (!criticalWarnedPositions.contains(position.getId())) {
                    createWarningEvent(position, distanceToLiq, currentPrice, liquidationPrice, "critical");
                    criticalWarnedPositions.add(position.getId());
                }
            } else if (distanceToLiq.compareTo(warningThreshold) < 0) {
                warningCount++;
                if (!warnedPositions.contains(position.getId())) {
                    createWarningEvent(position, distanceToLiq, currentPrice, liquidationPrice, "warning");
                    warnedPositions.add(position.getId());
                }
            } else {
                // Position is safe - remove from warned sets if it was there
                warnedPositions.remove(position.getId());
                criticalWarnedPositions.remove(position.getId());
            }
        }

        if (marginCallsExecuted > 0) {
            log.warn("Margin check complete: {} positions checked, {} margin calls executed", 
                    openPositions.size(), marginCallsExecuted);
        }

        return MarginCheckResult.builder()
                .positionsChecked(openPositions.size())
                .positionsWarning(warningCount)
                .positionsCritical(criticalCount)
                .marginCallsExecuted(marginCallsExecuted)
                .marginCalls(marginCalls)
                .build();
    }

    /**
     * Calculate the liquidation price for a position.
     * 
     * For LONG positions: price needs to drop by (1/leverage) to wipe out margin
     * liquidationPrice = entryPrice * (1 - 1/leverage)
     * 
     * For SHORT positions: price needs to rise by (1/leverage) to wipe out margin
     * liquidationPrice = entryPrice * (1 + 1/leverage)
     */
    public BigDecimal calculateLiquidationPrice(Position position) {
        BigDecimal entryPrice = position.getEntryPrice();
        int leverage = position.getLeverage();
        
        if (leverage <= 0) {
            leverage = 1; // Prevent division by zero
        }
        
        BigDecimal leverageFactor = BigDecimal.ONE.divide(
                BigDecimal.valueOf(leverage), 8, RoundingMode.HALF_UP);
        
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            // LONG: liquidation when price drops by margin percentage
            return entryPrice.multiply(BigDecimal.ONE.subtract(leverageFactor))
                    .setScale(8, RoundingMode.HALF_UP);
        } else {
            // SHORT: liquidation when price rises by margin percentage
            return entryPrice.multiply(BigDecimal.ONE.add(leverageFactor))
                    .setScale(8, RoundingMode.HALF_UP);
        }
    }

    /**
     * Calculate the distance to liquidation as a percentage.
     * Returns the percentage difference between current price and liquidation price.
     */
    public BigDecimal calculateDistanceToLiquidation(Position position, BigDecimal currentPrice, 
                                                      BigDecimal liquidationPrice) {
        if (currentPrice.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.valueOf(100); // Safe if no price
        }
        
        BigDecimal distance;
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            // For LONG: distance = (currentPrice - liquidationPrice) / currentPrice * 100
            distance = currentPrice.subtract(liquidationPrice)
                    .divide(currentPrice, 8, RoundingMode.HALF_UP)
                    .multiply(BigDecimal.valueOf(100));
        } else {
            // For SHORT: distance = (liquidationPrice - currentPrice) / currentPrice * 100
            distance = liquidationPrice.subtract(currentPrice)
                    .divide(currentPrice, 8, RoundingMode.HALF_UP)
                    .multiply(BigDecimal.valueOf(100));
        }
        
        return distance.setScale(2, RoundingMode.HALF_UP);
    }

    /**
     * Determine if a position should be liquidated based on current price.
     */
    private boolean shouldLiquidate(Position position, BigDecimal currentPrice, BigDecimal liquidationPrice) {
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            // LONG: liquidate if current price <= liquidation price
            return currentPrice.compareTo(liquidationPrice) <= 0;
        } else {
            // SHORT: liquidate if current price >= liquidation price
            return currentPrice.compareTo(liquidationPrice) >= 0;
        }
    }

    /**
     * Execute a margin call on a position.
     * Closes the position at the current market price and records the event.
     */
    private MarginCallInfo executeMarginCall(Position position, BigDecimal currentPrice, 
                                              BigDecimal liquidationPrice) {
        try {
            log.error("EXECUTING MARGIN CALL: {} {} at {} (liquidation: {})", 
                    position.getSymbol(), position.getDirection(), currentPrice, liquidationPrice);
            
            // Close the position using the margin call method
            PositionDTO closedPosition = positionService.closePositionMarginCall(
                    position.getId(), currentPrice);
            
            // Calculate loss amount
            BigDecimal lossAmount = closedPosition.getRealizedPnl();
            
            return MarginCallInfo.builder()
                    .positionId(position.getId())
                    .symbol(position.getSymbol())
                    .direction(position.getDirection())
                    .entryPrice(position.getEntryPrice())
                    .exitPrice(currentPrice)
                    .liquidationPrice(liquidationPrice)
                    .lossAmount(lossAmount)
                    .executedAt(Instant.now())
                    .build();
            
        } catch (Exception e) {
            log.error("Failed to execute margin call for position {}: {}", 
                    position.getId(), e.getMessage(), e);
            return null;
        }
    }

    /**
     * Log a warning for a position approaching liquidation.
     */
    private void createWarningEvent(Position position, BigDecimal distanceToLiq, 
                                     BigDecimal currentPrice, BigDecimal liquidationPrice,
                                     String severity) {
        log.warn("Margin {} for {} {}: distance to liquidation {}%, current: {}, liq: {}",
                severity.toUpperCase(), position.getSymbol(), position.getDirection(),
                distanceToLiq, currentPrice, liquidationPrice);
    }

    /**
     * Get live prices for a list of positions.
     */
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

    /**
     * Get margin health summary for all open positions.
     */
    public MarginHealthSummary getMarginHealthSummary() {
        List<Position> openPositions = positionRepository.findOpenPositions();
        if (openPositions.isEmpty()) {
            return MarginHealthSummary.builder()
                    .totalPositions(0)
                    .build();
        }

        Map<String, BigDecimal> livePrices = getLivePrices(openPositions);
        
        int safeCount = 0;
        int warningCount = 0;
        int dangerCount = 0;
        BigDecimal closestToLiq = null;

        for (Position position : openPositions) {
            BigDecimal currentPrice = livePrices.get(position.getSymbol());
            if (currentPrice == null) continue;

            BigDecimal liquidationPrice = calculateLiquidationPrice(position);
            BigDecimal distanceToLiq = calculateDistanceToLiquidation(position, currentPrice, liquidationPrice);

            if (closestToLiq == null || distanceToLiq.compareTo(closestToLiq) < 0) {
                closestToLiq = distanceToLiq;
            }

            if (distanceToLiq.compareTo(criticalThreshold) < 0) {
                dangerCount++;
            } else if (distanceToLiq.compareTo(warningThreshold) < 0) {
                warningCount++;
            } else {
                safeCount++;
            }
        }

        String overallStatus = dangerCount > 0 ? "danger" : 
                               warningCount > 0 ? "warning" : "safe";

        return MarginHealthSummary.builder()
                .totalPositions(openPositions.size())
                .positionsSafe(safeCount)
                .positionsWarning(warningCount)
                .positionsDanger(dangerCount)
                .closestToLiquidation(closestToLiq)
                .overallStatus(overallStatus)
                .build();
    }

    @lombok.Data
    @lombok.Builder
    public static class MarginHealthSummary {
        private int totalPositions;
        private int positionsSafe;
        private int positionsWarning;
        private int positionsDanger;
        private BigDecimal closestToLiquidation;
        private String overallStatus;
    }
}

