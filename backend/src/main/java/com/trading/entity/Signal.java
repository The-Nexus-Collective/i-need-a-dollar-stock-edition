package com.trading.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Trading signal entity
 * Maps to signals table
 */
@Entity
@Table(name = "signals")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Signal {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false)
    @Builder.Default
    private Instant timestamp = Instant.now();

    @Column(nullable = false, length = 10)
    private String coin;

    @Column(name = "sentiment_score", nullable = false, precision = 5, scale = 2)
    private BigDecimal sentimentScore;

    @Column(name = "narrative_strength", nullable = false, precision = 5, scale = 2)
    private BigDecimal narrativeStrength;

    @Column(name = "combined_score", nullable = false, precision = 8, scale = 4)
    private BigDecimal combinedScore;

    @Column(nullable = false, precision = 5, scale = 4)
    private BigDecimal confidence;

    @Column(name = "recommended_action", length = 20)
    private String recommendedAction;

    @Column(name = "raw_response", columnDefinition = "TEXT")
    private String rawResponse;

    @Column(name = "response_hash", length = 64)
    private String responseHash;

    @Column(name = "risk_approved")
    private Boolean riskApproved;

    @Column(name = "risk_rejection_reason", columnDefinition = "TEXT")
    private String riskRejectionReason;

    @Column
    @Builder.Default
    private Boolean executed = false;

    @Column(name = "leverage_calculated", precision = 4, scale = 1)
    private BigDecimal leverageCalculated;

    @Column(name = "market_regime", length = 20)
    private String marketRegime;

    @Column(name = "created_at")
    @Builder.Default
    private Instant createdAt = Instant.now();
}

