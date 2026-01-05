package com.trading.integration.grok.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Grok's decision for an existing position.
 * 
 * Actions:
 * - KEEP: Hold position unchanged
 * - CLOSE: Fully close the position
 * - EXTEND: Add to the position (scalePercent = % of current size to add)
 * - REDUCE: Partially close (scalePercent = % of current size to sell)
 * - INCREASE_LEVERAGE: Reduce margin, accept higher liquidation risk
 * - DECREASE_LEVERAGE: Increase margin, safer liquidation distance
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PositionDecision {
    
    public enum Action {
        KEEP, CLOSE, EXTEND, REDUCE,
        INCREASE_LEVERAGE, DECREASE_LEVERAGE
    }
    
    private String symbol;
    private Action action;
    private String reason;
    private int currentSentiment;  // -100 to +100
    private int scalePercent;      // For EXTEND/REDUCE: percentage to scale (10-100)
    private int targetLeverage;    // For INCREASE/DECREASE_LEVERAGE: new leverage (1-125)
    
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
                .targetLeverage(0)
                .build();
    }
    
    public static PositionDecision increaseLeverage(String symbol, String reason, int sentiment, int targetLeverage) {
        return PositionDecision.builder()
                .symbol(symbol)
                .action(Action.INCREASE_LEVERAGE)
                .reason(reason)
                .currentSentiment(sentiment)
                .scalePercent(0)
                .targetLeverage(Math.max(1, Math.min(125, targetLeverage)))
                .build();
    }
    
    public static PositionDecision decreaseLeverage(String symbol, String reason, int sentiment, int targetLeverage) {
        return PositionDecision.builder()
                .symbol(symbol)
                .action(Action.DECREASE_LEVERAGE)
                .reason(reason)
                .currentSentiment(sentiment)
                .scalePercent(0)
                .targetLeverage(Math.max(1, Math.min(125, targetLeverage)))
                .build();
    }
}

