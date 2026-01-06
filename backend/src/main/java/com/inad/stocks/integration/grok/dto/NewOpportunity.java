package com.inad.stocks.integration.grok.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.util.List;

/**
 * AI recommendation for a new stock trade.
 * 
 * Includes Pre-Mortem data for the self-learning system:
 * - preMortem: What could cause this trade to fail
 * - bullCase: Why this trade should succeed
 * - bearCase: Counter-argument (devil's advocate)
 * - Expected hold time and PnL targets
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class NewOpportunity {
    
    public enum Direction {
        LONG, SHORT
    }
    
    private String symbol;
    private Direction direction;
    private String sector;            // TECH or DEFENSE
    private int conviction;           // 0-100
    private int sentimentScore;       // -100 to +100
    private int narrativeStrength;    // 0-100
    private String reason;
    private List<String> keySignals;
    
    /**
     * Position size as percentage of available capital (1-100).
     * Determined by Grok based on conviction and market conditions.
     * No upper limit - Grok decides how aggressively to size positions.
     */
    private Integer positionSizePercent;
    
    // ========== Self-Learning Pre-Mortem Fields ==========
    
    /**
     * Pre-Mortem: What could cause this trade to fail.
     * "This trade FAILS if: [condition]"
     */
    private String preMortem;
    
    /**
     * Bull case: Why this trade should succeed.
     */
    private String bullCase;
    
    /**
     * Bear case: Counter-argument / devil's advocate.
     */
    private String bearCase;
    
    /**
     * Expected minimum hold time in hours.
     */
    private Integer expectedHoldHoursMin;
    
    /**
     * Expected maximum hold time in hours.
     */
    private Integer expectedHoldHoursMax;
    
    /**
     * Target PnL percentage for this trade.
     */
    private BigDecimal targetPnlPercent;
    
    /**
     * Maximum acceptable loss percentage.
     */
    private BigDecimal maxAcceptableLossPercent;
    
    /**
     * Check if this opportunity meets minimum conviction threshold
     */
    public boolean meetsConvictionThreshold(int threshold) {
        return conviction >= threshold;
    }
    
    /**
     * Check if this opportunity can replace an existing position
     * (conviction must be at least +25 higher)
     */
    public boolean canReplace(int existingConviction) {
        return conviction >= existingConviction + 25;
    }
    
    /**
     * Check if this opportunity has Pre-Mortem data.
     */
    public boolean hasPreMortem() {
        return preMortem != null && !preMortem.isEmpty();
    }
}

