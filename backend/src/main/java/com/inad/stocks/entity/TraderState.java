package com.inad.stocks.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Trader state singleton entity
 * Maps to trader_state table
 */
@Entity
@Table(name = "trader_state")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TraderState {

    @Id
    @Column(length = 50)
    @Builder.Default
    private String id = "main";

    @Column(name = "current_capital", nullable = false, precision = 18, scale = 2)
    @Builder.Default
    private BigDecimal currentCapital = BigDecimal.ZERO;

    @Column(name = "starting_capital", nullable = false, precision = 18, scale = 2)
    @Builder.Default
    private BigDecimal startingCapital = BigDecimal.ZERO;

    @Column(name = "total_cycles")
    @Builder.Default
    private Integer totalCycles = 0;

    @Column(name = "total_trades")
    @Builder.Default
    private Integer totalTrades = 0;

    @Column(name = "winning_trades")
    @Builder.Default
    private Integer winningTrades = 0;

    @Column(name = "losing_trades")
    @Builder.Default
    private Integer losingTrades = 0;

    @Column(name = "total_pnl", precision = 18, scale = 4)
    @Builder.Default
    private BigDecimal totalPnl = BigDecimal.ZERO;

    @Column(name = "max_drawdown", precision = 8, scale = 4)
    @Builder.Default
    private BigDecimal maxDrawdown = BigDecimal.ZERO;

    @Column(name = "peak_capital", precision = 18, scale = 2)
    @Builder.Default
    private BigDecimal peakCapital = BigDecimal.ZERO;

    @Column(name = "total_fees_paid", precision = 18, scale = 4)
    @Builder.Default
    private BigDecimal totalFeesPaid = BigDecimal.ZERO;
    
    @Column(name = "total_slippage_cost", precision = 18, scale = 4)
    @Builder.Default
    private BigDecimal totalSlippageCost = BigDecimal.ZERO;

    @Column(name = "last_cycle_at")
    private Instant lastCycleAt;

    @Column(name = "created_at")
    @Builder.Default
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at")
    @Builder.Default
    private Instant updatedAt = Instant.now();

    @Transient
    public BigDecimal getTotalReturn() {
        if (startingCapital.compareTo(BigDecimal.ZERO) == 0) return BigDecimal.ZERO;
        return currentCapital.subtract(startingCapital)
                .divide(startingCapital, 4, java.math.RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));
    }

    @Transient
    public BigDecimal getWinRate() {
        if (totalTrades == 0) return BigDecimal.ZERO;
        return BigDecimal.valueOf(winningTrades)
                .divide(BigDecimal.valueOf(totalTrades), 4, java.math.RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));
    }

    @PreUpdate
    public void preUpdate() {
        this.updatedAt = Instant.now();
    }
}

