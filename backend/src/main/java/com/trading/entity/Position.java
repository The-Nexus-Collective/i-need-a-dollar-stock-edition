package com.trading.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Paper trading position entity
 * Maps to paper_positions table
 */
@Entity
@Table(name = "paper_positions")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Position {

    @Id
    @Column(length = 32)
    private String id;

    @Column(nullable = false, length = 20)
    private String symbol;

    @Column(nullable = false, length = 10)
    private String direction;

    @Column(name = "entry_price", nullable = false, precision = 20, scale = 8)
    private BigDecimal entryPrice;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal quantity;

    @Column(name = "size_usdt", nullable = false, precision = 20, scale = 2)
    private BigDecimal sizeUsdt;

    @Column
    @Builder.Default
    private Integer leverage = 10;

    @Column(name = "stop_loss_price", precision = 20, scale = 8)
    private BigDecimal stopLossPrice;

    @Column(name = "take_profit_price", precision = 20, scale = 8)
    private BigDecimal takeProfitPrice;

    @Column(length = 20)
    @Builder.Default
    private String status = "OPEN";

    @Column(name = "entry_time")
    @Builder.Default
    private Instant entryTime = Instant.now();

    @Column(name = "exit_time")
    private Instant exitTime;

    @Column(name = "exit_price", precision = 20, scale = 8)
    private BigDecimal exitPrice;

    @Column(name = "realized_pnl", precision = 20, scale = 2)
    @Builder.Default
    private BigDecimal realizedPnl = BigDecimal.ZERO;

    @Column(precision = 5, scale = 2)
    @Builder.Default
    private BigDecimal conviction = BigDecimal.ZERO;

    @Column(columnDefinition = "TEXT")
    private String reasoning;

    @Column(name = "prediction_id")
    private String predictionId;

    @Column(name = "created_at")
    @Builder.Default
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at")
    @Builder.Default
    private Instant updatedAt = Instant.now();

    @Transient
    private BigDecimal currentPrice;

    @Transient
    private BigDecimal unrealizedPnl;

    /**
     * Calculate unrealized PnL for open position
     */
    public BigDecimal calculateUnrealizedPnl(BigDecimal price) {
        if (price == null || this.entryPrice == null) return BigDecimal.ZERO;
        
        BigDecimal priceDiff = price.subtract(this.entryPrice);
        if ("SHORT".equalsIgnoreCase(direction)) {
            priceDiff = priceDiff.negate();
        }
        
        return priceDiff.multiply(quantity).multiply(BigDecimal.valueOf(leverage));
    }

    /**
     * Calculate PnL percentage
     */
    public BigDecimal calculatePnlPercent(BigDecimal price) {
        if (price == null || this.entryPrice == null || this.entryPrice.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal pnl = calculateUnrealizedPnl(price);
        return pnl.divide(this.sizeUsdt, 4, java.math.RoundingMode.HALF_UP)
                  .multiply(BigDecimal.valueOf(100));
    }

    @PreUpdate
    public void preUpdate() {
        this.updatedAt = Instant.now();
    }
}

