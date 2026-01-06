package com.inad.stocks.entity;

import com.inad.stocks.entity.enums.Exchange;
import com.inad.stocks.entity.enums.Sector;
import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Stock trading position entity
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

    @Column(nullable = false, precision = 20, scale = 0)
    private BigDecimal quantity;  // Whole shares only - no fractional shares

    @Column(name = "size_usd", nullable = false, precision = 20, scale = 2)
    private BigDecimal sizeUsd;

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

    // ========== Stock-specific Fields ==========
    
    /**
     * Stock exchange (NYSE, NASDAQ, etc.)
     */
    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    @Builder.Default
    private Exchange exchange = Exchange.UNKNOWN;
    
    /**
     * Stock sector (TECH, DEFENSE, etc.)
     */
    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    @Builder.Default
    private Sector sector = Sector.OTHER;

    @Column(name = "created_at")
    @Builder.Default
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at")
    @Builder.Default
    private Instant updatedAt = Instant.now();

    // ========== Self-Learning Pre-Mortem Fields ==========
    
    /**
     * Pre-Mortem: AI's prediction of what could cause this trade to fail.
     */
    @Column(name = "pre_mortem", columnDefinition = "TEXT")
    private String preMortem;
    
    /**
     * Bull case: Why this trade should succeed.
     */
    @Column(name = "bull_case", columnDefinition = "TEXT")
    private String bullCase;
    
    /**
     * Bear case: Counter-argument / devil's advocate.
     */
    @Column(name = "bear_case", columnDefinition = "TEXT")
    private String bearCase;
    
    /**
     * Expected minimum hold time in hours.
     */
    @Column(name = "expected_hold_hours_min")
    private Integer expectedHoldHoursMin;
    
    /**
     * Expected maximum hold time in hours.
     */
    @Column(name = "expected_hold_hours_max")
    private Integer expectedHoldHoursMax;
    
    /**
     * Target PnL percentage for this trade.
     */
    @Column(name = "target_pnl_percent", precision = 10, scale = 4)
    private BigDecimal targetPnlPercent;
    
    /**
     * Maximum acceptable loss percentage.
     */
    @Column(name = "max_acceptable_loss_percent", precision = 10, scale = 4)
    private BigDecimal maxAcceptableLossPercent;

    @Transient
    private BigDecimal currentPrice;

    @Transient
    private BigDecimal unrealizedPnl;

    /**
     * Calculate unrealized PnL for open position.
     */
    public BigDecimal calculateUnrealizedPnl(BigDecimal price) {
        if (price == null || this.entryPrice == null) return BigDecimal.ZERO;
        
        BigDecimal priceDiff = price.subtract(this.entryPrice);
        if ("SHORT".equalsIgnoreCase(direction)) {
            priceDiff = priceDiff.negate();
        }
        
        return priceDiff.multiply(quantity);
    }

    /**
     * Calculate PnL percentage
     */
    public BigDecimal calculatePnlPercent(BigDecimal price) {
        if (price == null || this.entryPrice == null || this.entryPrice.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal pnl = calculateUnrealizedPnl(price);
        return pnl.divide(this.sizeUsd, 4, java.math.RoundingMode.HALF_UP)
                  .multiply(BigDecimal.valueOf(100));
    }

    @PreUpdate
    public void preUpdate() {
        this.updatedAt = Instant.now();
    }
}

