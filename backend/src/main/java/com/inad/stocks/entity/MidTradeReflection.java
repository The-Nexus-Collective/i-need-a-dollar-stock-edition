package com.inad.stocks.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Records mid-trade evaluations of open positions against their Pre-Mortem predictions.
 * 
 * Unlike ReflectionEntry (which is created when trades close), this captures
 * how positions are performing WHILE they are still open.
 */
@Entity
@Table(name = "mid_trade_reflections")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MidTradeReflection {

    @Id
    private String id;

    @Column(name = "position_id", nullable = false)
    private String positionId;

    @Column(nullable = false, length = 20)
    private String symbol;

    @Column(nullable = false, length = 10)
    private String direction;

    @Column(name = "evaluated_at", nullable = false)
    private Instant evaluatedAt;

    // Current state at evaluation time
    @Column(name = "current_price", precision = 20, scale = 8)
    private BigDecimal currentPrice;

    @Column(name = "current_pnl_percent", precision = 10, scale = 4)
    private BigDecimal currentPnlPercent;

    @Column(name = "current_hold_hours")
    private Integer currentHoldHours;

    // Pre-Mortem expectations
    @Column(name = "target_pnl_percent", precision = 10, scale = 4)
    private BigDecimal targetPnlPercent;

    @Column(name = "max_acceptable_loss", precision = 10, scale = 4)
    private BigDecimal maxAcceptableLoss;

    @Column(name = "expected_hold_hours_max")
    private Integer expectedHoldHoursMax;

    // Evaluation results
    @Column(name = "within_pnl_expectations")
    private Boolean withinPnlExpectations;

    @Column(name = "within_time_expectations")
    private Boolean withinTimeExpectations;

    @Column(name = "approaching_max_loss")
    private Boolean approachingMaxLoss;

    @Column(name = "exceeding_target")
    private Boolean exceedingTarget;

    // Health assessment
    @Column(name = "health_status", length = 20)
    @Enumerated(EnumType.STRING)
    private HealthStatus healthStatus;

    @Column(length = 30)
    private String recommendation;

    @Column(name = "health_reason", columnDefinition = "TEXT")
    private String healthReason;

    // Pre-Mortem content for reference
    @Column(name = "pre_mortem", columnDefinition = "TEXT")
    private String preMortem;

    @Column(name = "bear_case", columnDefinition = "TEXT")
    private String bearCase;

    // Whether this evaluation led to an action
    @Column(name = "action_taken", length = 30)
    private String actionTaken;

    @Column(name = "cycle_number")
    private Integer cycleNumber;

    public enum HealthStatus {
        HEALTHY,
        WARNING,
        DANGER
    }
}

