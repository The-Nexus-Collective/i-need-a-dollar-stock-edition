package com.inad.stocks.entity;

import com.inad.stocks.entity.enums.Sector;
import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Stock trade entity - completed trades with entry and exit
 * Maps to paper_trades table
 */
@Entity
@Table(name = "paper_trades")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Trade {

    @Id
    @Column(length = 32)
    private String id;

    @Column(name = "position_id", length = 32)
    private String positionId;

    @Column(nullable = false, length = 20)
    private String symbol;

    @Column(nullable = false, length = 10)
    private String direction;

    @Column(name = "entry_price", nullable = false, precision = 20, scale = 8)
    private BigDecimal entryPrice;

    @Column(name = "exit_price", nullable = false, precision = 20, scale = 8)
    private BigDecimal exitPrice;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal quantity;

    @Column(name = "size_usd", nullable = false, precision = 20, scale = 2)
    private BigDecimal sizeUsd;

    @Column(name = "pnl_usd", nullable = false, precision = 20, scale = 2)
    private BigDecimal pnlUsd;

    @Column(name = "pnl_percent", nullable = false, precision = 10, scale = 4)
    private BigDecimal pnlPercent;

    @Column(name = "entry_time", nullable = false)
    private Instant entryTime;

    @Column(name = "exit_time", nullable = false)
    private Instant exitTime;

    @Column(name = "duration_seconds")
    private Integer durationSeconds;

    @Column(name = "exit_reason", nullable = false, length = 100)
    private String exitReason;

    @Column(precision = 5, scale = 2)
    @Builder.Default
    private BigDecimal conviction = BigDecimal.ZERO;

    @Column(columnDefinition = "TEXT")
    private String reasoning;

    @Column(name = "entry_fee", precision = 20, scale = 8)
    private BigDecimal entryFee;

    @Column(name = "exit_fee", precision = 20, scale = 8)
    private BigDecimal exitFee;

    @Column(name = "total_fees", precision = 20, scale = 8)
    private BigDecimal totalFees;
    
    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    @Builder.Default
    private Sector sector = Sector.OTHER;

    @Column(name = "created_at")
    @Builder.Default
    private Instant createdAt = Instant.now();

    public boolean isWinning() {
        return pnlUsd != null && pnlUsd.compareTo(BigDecimal.ZERO) > 0;
    }
}

