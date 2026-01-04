package com.trading.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Prediction entity - individual coin predictions for each cycle
 * Maps to predictions table
 */
@Entity
@Table(name = "predictions")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Prediction {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "cycle_id")
    private UUID cycleId;

    @Column(nullable = false, length = 20)
    private String coin;

    @Column(nullable = false, length = 10)
    private String direction;

    @Column(nullable = false)
    private Integer conviction;

    @Column(nullable = false, precision = 4, scale = 2)
    private BigDecimal leverage;

    @Column(columnDefinition = "TEXT")
    private String reason;

    @Column(name = "position_id", length = 50)
    private String positionId;

    @Column(name = "entry_price", precision = 18, scale = 8)
    private BigDecimal entryPrice;

    @Column(precision = 18, scale = 8)
    private BigDecimal quantity;

    @Column(name = "size_usdt", precision = 18, scale = 2)
    private BigDecimal sizeUsdt;

    @Column(name = "exit_price", precision = 18, scale = 8)
    private BigDecimal exitPrice;

    @Column(precision = 18, scale = 4)
    private BigDecimal pnl;

    @Column(name = "pnl_pct", precision = 8, scale = 4)
    private BigDecimal pnlPct;

    @Column(name = "created_at")
    @Builder.Default
    private Instant createdAt = Instant.now();
}

