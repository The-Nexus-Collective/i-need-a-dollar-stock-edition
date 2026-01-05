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

    // ========== Margin System Fields ==========
    
    /**
     * Margin mode: ISOLATED (per position) or CROSS (shared).
     * Currently only ISOLATED is supported.
     */
    @Column(name = "margin_mode", length = 10)
    @Builder.Default
    private String marginMode = "ISOLATED";
    
    /**
     * Isolated margin allocated to this position.
     * Calculated as: sizeUsdt / leverage
     */
    @Column(name = "isolated_margin", precision = 20, scale = 8)
    private BigDecimal isolatedMargin;
    
    /**
     * Maintenance Margin Rate from Binance bracket.
     * Default 0.4% for small positions.
     */
    @Column(name = "maint_margin_rate", precision = 10, scale = 6)
    @Builder.Default
    private BigDecimal maintMarginRate = new BigDecimal("0.004");
    
    /**
     * Calculated liquidation price based on leverage and MMR.
     * LONG: entry * (1 - 1/leverage + MMR)
     * SHORT: entry * (1 + 1/leverage - MMR)
     */
    @Column(name = "liquidation_price", precision = 20, scale = 8)
    private BigDecimal liquidationPrice;

    @Column(name = "created_at")
    @Builder.Default
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at")
    @Builder.Default
    private Instant updatedAt = Instant.now();

    // ========== Self-Learning Pre-Mortem Fields ==========
    
    /**
     * Pre-Mortem: Grok's prediction of what could cause this trade to fail.
     * Written before trade entry, evaluated after trade exit.
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
     * 
     * Note: PnL = priceDiff * quantity
     * The leverage is NOT multiplied here because:
     * - quantity = sizeUsdt (notional) / price
     * - The notional already represents the full leveraged position size
     * - Multiplying by leverage again would be double-counting
     * 
     * Example: $2000 margin with 10x leverage = $20,000 notional
     * - quantity = 20000 / 50000 = 0.4 BTC
     * - If price rises 10% to $55,000: PnL = 5000 * 0.4 = $2000 (100% return on margin)
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
        return pnl.divide(this.sizeUsdt, 4, java.math.RoundingMode.HALF_UP)
                  .multiply(BigDecimal.valueOf(100));
    }

    @PreUpdate
    public void preUpdate() {
        this.updatedAt = Instant.now();
    }
}

