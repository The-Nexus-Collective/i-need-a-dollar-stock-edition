package com.inad.stocks.service;

import com.inad.stocks.entity.Position;
import com.inad.stocks.integration.broker.StockBrokerClient;
import com.inad.stocks.repository.PositionRepository;
import lombok.Builder;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Evaluates open positions against their Pre-Mortem predictions.
 * 
 * Provides mid-trade health checks to identify:
 * - Positions deviating from PnL expectations
 * - Positions exceeding expected hold time
 * - Positions where Bear Case might be materializing
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class OpenPositionEvaluator {

    private final PositionRepository positionRepository;
    private final StockBrokerClient stockBrokerClient;

    /**
     * Result of evaluating an open position against its Pre-Mortem.
     */
    @Data
    @Builder
    public static class PositionHealthCheck {
        private String positionId;
        private String symbol;
        private String direction;
        
        // Current state
        private BigDecimal currentPrice;
        private BigDecimal currentPnlPercent;
        private int currentHoldHours;
        
        // Pre-Mortem expectations
        private BigDecimal targetPnlPercent;
        private BigDecimal maxAcceptableLoss;
        private Integer expectedHoldHoursMin;
        private Integer expectedHoldHoursMax;
        private String preMortem;
        private String bearCase;
        private String bullCase;
        
        // Evaluation results
        private boolean withinPnlExpectations;
        private boolean withinTimeExpectations;
        private boolean approachingMaxLoss;
        private boolean exceedingTargetPnl;
        
        // Overall assessment
        private HealthStatus healthStatus;
        private String recommendation;
        private String healthReason;
        
        public enum HealthStatus {
            HEALTHY,    // Within all expectations
            WARNING,    // Some expectations breached
            DANGER      // Critical - action needed
        }
    }

    /**
     * Evaluate all open positions against their Pre-Mortem predictions.
     */
    public List<PositionHealthCheck> evaluateOpenPositions() {
        List<Position> openPositions = positionRepository.findOpenPositions();
        
        return openPositions.stream()
                .filter(p -> p.getPreMortem() != null || p.getTargetPnlPercent() != null)
                .map(this::evaluatePosition)
                .collect(Collectors.toList());
    }

    /**
     * Evaluate a single position against its Pre-Mortem.
     */
    public PositionHealthCheck evaluatePosition(Position position) {
        BigDecimal currentPrice = stockBrokerClient.getPrice(position.getSymbol());
        return evaluatePosition(position, currentPrice);
    }

    /**
     * Evaluate a single position with a given current price.
     */
    public PositionHealthCheck evaluatePosition(Position position, BigDecimal currentPrice) {
        // Calculate current PnL
        BigDecimal pnlPercent = calculatePnlPercent(position, currentPrice);
        
        // Calculate hold time
        Duration holdTime = Duration.between(position.getEntryTime(), Instant.now());
        int holdHours = (int) holdTime.toHours();
        
        // Check PnL expectations
        boolean withinPnlExpectations = true;
        boolean approachingMaxLoss = false;
        boolean exceedingTargetPnl = false;
        
        if (position.getMaxAcceptableLossPercent() != null) {
            BigDecimal maxLoss = position.getMaxAcceptableLossPercent().negate();
            approachingMaxLoss = pnlPercent.compareTo(maxLoss.multiply(BigDecimal.valueOf(0.7))) <= 0;
            withinPnlExpectations = pnlPercent.compareTo(maxLoss) > 0;
        }
        
        if (position.getTargetPnlPercent() != null) {
            exceedingTargetPnl = pnlPercent.compareTo(position.getTargetPnlPercent()) >= 0;
        }
        
        // Check time expectations
        boolean withinTimeExpectations = true;
        if (position.getExpectedHoldHoursMax() != null) {
            withinTimeExpectations = holdHours <= position.getExpectedHoldHoursMax();
        }
        
        // Determine health status and recommendation
        HealthCheckResult result = determineHealthStatus(
                pnlPercent, holdHours, position,
                withinPnlExpectations, withinTimeExpectations,
                approachingMaxLoss, exceedingTargetPnl
        );
        
        return PositionHealthCheck.builder()
                .positionId(position.getId())
                .symbol(position.getSymbol())
                .direction(position.getDirection())
                .currentPrice(currentPrice)
                .currentPnlPercent(pnlPercent)
                .currentHoldHours(holdHours)
                .targetPnlPercent(position.getTargetPnlPercent())
                .maxAcceptableLoss(position.getMaxAcceptableLossPercent())
                .expectedHoldHoursMin(position.getExpectedHoldHoursMin())
                .expectedHoldHoursMax(position.getExpectedHoldHoursMax())
                .preMortem(position.getPreMortem())
                .bearCase(position.getBearCase())
                .bullCase(position.getBullCase())
                .withinPnlExpectations(withinPnlExpectations)
                .withinTimeExpectations(withinTimeExpectations)
                .approachingMaxLoss(approachingMaxLoss)
                .exceedingTargetPnl(exceedingTargetPnl)
                .healthStatus(result.status)
                .recommendation(result.recommendation)
                .healthReason(result.reason)
                .build();
    }

    @Data
    @Builder
    private static class HealthCheckResult {
        PositionHealthCheck.HealthStatus status;
        String recommendation;
        String reason;
    }

    private HealthCheckResult determineHealthStatus(
            BigDecimal pnlPercent, int holdHours, Position position,
            boolean withinPnlExpectations, boolean withinTimeExpectations,
            boolean approachingMaxLoss, boolean exceedingTargetPnl) {
        
        // DANGER conditions
        if (!withinPnlExpectations) {
            return HealthCheckResult.builder()
                    .status(PositionHealthCheck.HealthStatus.DANGER)
                    .recommendation("CLOSE_RECOMMENDED")
                    .reason(String.format("PnL %.1f%% exceeds max acceptable loss %.1f%%",
                            pnlPercent, position.getMaxAcceptableLossPercent().negate()))
                    .build();
        }
        
        // WARNING conditions
        if (approachingMaxLoss) {
            return HealthCheckResult.builder()
                    .status(PositionHealthCheck.HealthStatus.WARNING)
                    .recommendation("REVIEW")
                    .reason(String.format("PnL %.1f%% approaching max loss threshold (70%% of limit)",
                            pnlPercent))
                    .build();
        }
        
        if (!withinTimeExpectations) {
            int overTime = holdHours - position.getExpectedHoldHoursMax();
            return HealthCheckResult.builder()
                    .status(PositionHealthCheck.HealthStatus.WARNING)
                    .recommendation("REVIEW")
                    .reason(String.format("Hold time %dh exceeds expected max %dh by %dh",
                            holdHours, position.getExpectedHoldHoursMax(), overTime))
                    .build();
        }
        
        // Check for profit taking opportunity
        if (exceedingTargetPnl) {
            return HealthCheckResult.builder()
                    .status(PositionHealthCheck.HealthStatus.HEALTHY)
                    .recommendation("TAKE_PROFIT")
                    .reason(String.format("PnL %.1f%% exceeds target %.1f%% - consider taking profits",
                            pnlPercent, position.getTargetPnlPercent()))
                    .build();
        }
        
        // HEALTHY
        return HealthCheckResult.builder()
                .status(PositionHealthCheck.HealthStatus.HEALTHY)
                .recommendation("HOLD")
                .reason("Within all Pre-Mortem expectations")
                .build();
    }

    private BigDecimal calculatePnlPercent(Position position, BigDecimal currentPrice) {
        if (currentPrice == null || position.getEntryPrice() == null || 
            position.getSizeUsd() == null || position.getSizeUsd().compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal priceDiff;
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            priceDiff = currentPrice.subtract(position.getEntryPrice());
        } else {
            priceDiff = position.getEntryPrice().subtract(currentPrice);
        }
        
        BigDecimal pnl = priceDiff.multiply(position.getQuantity());
        return pnl.divide(position.getSizeUsd(), 4, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));
    }

    /**
     * Build a formatted context string for Grok prompt.
     */
    public String buildHealthContext(List<PositionHealthCheck> healthChecks) {
        if (healthChecks.isEmpty()) {
            return "";
        }

        StringBuilder sb = new StringBuilder();
        sb.append("\n═══════════════════════════════════════════════════════════════════\n");
        sb.append("PRE-MORTEM HEALTH CHECK (vs. your predictions)\n");
        sb.append("═══════════════════════════════════════════════════════════════════\n\n");

        // Group by health status
        List<PositionHealthCheck> dangerChecks = healthChecks.stream()
                .filter(h -> h.getHealthStatus() == PositionHealthCheck.HealthStatus.DANGER)
                .toList();
        
        List<PositionHealthCheck> warningChecks = healthChecks.stream()
                .filter(h -> h.getHealthStatus() == PositionHealthCheck.HealthStatus.WARNING)
                .toList();
        
        List<PositionHealthCheck> healthyChecks = healthChecks.stream()
                .filter(h -> h.getHealthStatus() == PositionHealthCheck.HealthStatus.HEALTHY)
                .toList();

        if (!dangerChecks.isEmpty()) {
            sb.append("🔴 DANGER - Action Required:\n");
            for (PositionHealthCheck check : dangerChecks) {
                appendHealthCheck(sb, check);
            }
            sb.append("\n");
        }

        if (!warningChecks.isEmpty()) {
            sb.append("🟡 WARNING - Review Needed:\n");
            for (PositionHealthCheck check : warningChecks) {
                appendHealthCheck(sb, check);
            }
            sb.append("\n");
        }

        if (!healthyChecks.isEmpty()) {
            sb.append("🟢 HEALTHY - On Track:\n");
            for (PositionHealthCheck check : healthyChecks) {
                appendHealthCheckBrief(sb, check);
            }
        }

        return sb.toString();
    }

    private void appendHealthCheck(StringBuilder sb, PositionHealthCheck check) {
        sb.append(String.format("- %s %s: PnL %.1f%%", 
                check.getSymbol(), check.getDirection(), check.getCurrentPnlPercent()));
        
        if (check.getTargetPnlPercent() != null) {
            sb.append(String.format(" (target: +%.1f%%)", check.getTargetPnlPercent()));
        }
        if (check.getMaxAcceptableLoss() != null) {
            sb.append(String.format(" (max loss: -%.1f%%)", check.getMaxAcceptableLoss()));
        }
        
        sb.append(String.format(", hold: %dh", check.getCurrentHoldHours()));
        if (check.getExpectedHoldHoursMax() != null) {
            sb.append(String.format(" (expected max: %dh)", check.getExpectedHoldHoursMax()));
        }
        sb.append("\n");
        
        sb.append(String.format("  → %s: %s\n", check.getRecommendation(), check.getHealthReason()));
        
        if (check.getBearCase() != null && !check.isWithinPnlExpectations()) {
            sb.append(String.format("  Bear Case was: \"%s\"\n", check.getBearCase()));
        }
    }

    private void appendHealthCheckBrief(StringBuilder sb, PositionHealthCheck check) {
        sb.append(String.format("- %s: PnL %.1f%%, hold %dh - %s\n",
                check.getSymbol(), check.getCurrentPnlPercent(), 
                check.getCurrentHoldHours(), check.getRecommendation()));
    }

    /**
     * Get summary statistics for dashboard.
     */
    public HealthSummary getHealthSummary() {
        List<PositionHealthCheck> checks = evaluateOpenPositions();
        
        int healthy = (int) checks.stream()
                .filter(c -> c.getHealthStatus() == PositionHealthCheck.HealthStatus.HEALTHY)
                .count();
        int warning = (int) checks.stream()
                .filter(c -> c.getHealthStatus() == PositionHealthCheck.HealthStatus.WARNING)
                .count();
        int danger = (int) checks.stream()
                .filter(c -> c.getHealthStatus() == PositionHealthCheck.HealthStatus.DANGER)
                .count();
        
        return HealthSummary.builder()
                .totalEvaluated(checks.size())
                .healthy(healthy)
                .warning(warning)
                .danger(danger)
                .checks(checks)
                .build();
    }

    @Data
    @Builder
    public static class HealthSummary {
        private int totalEvaluated;
        private int healthy;
        private int warning;
        private int danger;
        private List<PositionHealthCheck> checks;
    }
}

