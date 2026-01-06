package com.inad.stocks.integration.grok.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * AI decision for an existing stock position.
 * 
 * Actions:
 * - KEEP: Hold position unchanged
 * - CLOSE: Fully close the position
 * - EXTEND: Add to the position (scalePercent = % of current size to add)
 * - REDUCE: Partially close (scalePercent = % of current size to sell)
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PositionDecision {
    
    public enum Action {
        KEEP, CLOSE, EXTEND, REDUCE
    }
    
    private String symbol;
    private Action action;
    private String reason;
    private int currentSentiment;  // -100 to +100
    private int scalePercent;      // For EXTEND/REDUCE: percentage to scale (10-100)
    
    public static PositionDecision keep(String symbol, String reason, int sentiment) {
        return PositionDecision.builder()
                .symbol(symbol)
                .action(Action.KEEP)
                .reason(reason)
                .currentSentiment(sentiment)
                .scalePercent(0)
                .build();
    }
    
    public static PositionDecision close(String symbol, String reason, int sentiment) {
        return PositionDecision.builder()
                .symbol(symbol)
                .action(Action.CLOSE)
                .reason(reason)
                .currentSentiment(sentiment)
                .scalePercent(0)
                .build();
    }
    
    public static PositionDecision extend(String symbol, String reason, int sentiment, int scalePercent) {
        return PositionDecision.builder()
                .symbol(symbol)
                .action(Action.EXTEND)
                .reason(reason)
                .currentSentiment(sentiment)
                .scalePercent(Math.max(10, Math.min(100, scalePercent)))
                .build();
    }
    
    public static PositionDecision reduce(String symbol, String reason, int sentiment, int scalePercent) {
        return PositionDecision.builder()
                .symbol(symbol)
                .action(Action.REDUCE)
                .reason(reason)
                .currentSentiment(sentiment)
                .scalePercent(Math.max(10, Math.min(100, scalePercent)))
                .build();
    }
}

