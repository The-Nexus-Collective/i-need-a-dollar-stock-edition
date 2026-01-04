package com.trading.integration.grok.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Grok's recommendation for a new trade.
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
    private int conviction;          // 0-100
    private int leverage;            // 1-10
    private int sentimentScore;      // -100 to +100
    private int narrativeStrength;   // 0-100
    private String reason;
    private List<String> keySignals;
    
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
}

