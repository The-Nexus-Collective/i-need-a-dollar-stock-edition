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
import java.util.List;
import java.util.UUID;

/**
 * Prediction cycle entity - 15-minute trading cycles
 * Maps to prediction_cycles table
 */
@Entity
@Table(name = "prediction_cycles")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PredictionCycle {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "cycle_number", nullable = false)
    private Integer cycleNumber;

    @Column(name = "started_at", nullable = false)
    @Builder.Default
    private Instant startedAt = Instant.now();

    @Column(name = "completed_at")
    private Instant completedAt;

    @Column(name = "capital_before", nullable = false, precision = 18, scale = 2)
    private BigDecimal capitalBefore;

    @Column(name = "capital_after", precision = 18, scale = 2)
    private BigDecimal capitalAfter;

    @Column(name = "total_pnl", precision = 18, scale = 4)
    private BigDecimal totalPnl;

    @Column(name = "coins_traded", columnDefinition = "TEXT[]")
    @JdbcTypeCode(SqlTypes.ARRAY)
    private String[] coinsTraded;

    @Column(length = 20)
    @Builder.Default
    private String status = "running";

    @Column(name = "created_at")
    @Builder.Default
    private Instant createdAt = Instant.now();
}

