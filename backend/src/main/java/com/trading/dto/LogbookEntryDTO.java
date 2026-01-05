package com.trading.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Value;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

/**
 * DTO for logbook entries - matches frontend expectations
 */
@Value
@Builder
public class LogbookEntryDTO {
    String id;
    Instant timestamp;
    
    @JsonProperty("cycle_number")
    int cycleNumber;
    
    @JsonProperty("analysis_text")
    String analysisText;
    
    @JsonProperty("market_summary")
    String marketSummary;
    
    @JsonProperty("positions_closed")
    List<PositionAction> positionsClosed;
    
    @JsonProperty("positions_opened")
    List<PositionAction> positionsOpened;
    
    @JsonProperty("positions_kept")
    List<String> positionsKept;
    
    @JsonProperty("positions_extended")
    List<ScaledPositionAction> positionsExtended;
    
    @JsonProperty("positions_reduced")
    List<ScaledPositionAction> positionsReduced;
    
    @JsonProperty("coins_analyzed")
    int coinsAnalyzed;
    
    @JsonProperty("coins_skipped")
    int coinsSkipped;
    
    @JsonProperty("tokens_used")
    int tokensUsed;
    
    @JsonProperty("total_equity")
    BigDecimal totalEquity;
    
    @JsonProperty("unrealized_pnl")
    BigDecimal unrealizedPnl;
    
    @JsonProperty("open_positions")
    int openPositions;
    
    @JsonProperty("deployment_percent")
    BigDecimal deploymentPercent;
    
    @JsonProperty("raw_prompt")
    String rawPrompt;
    
    @JsonProperty("raw_response")
    String rawResponse;
    
    @Value
    @Builder
    public static class PositionAction {
        String symbol;
        String direction;
        String reason;
        int conviction;
        int leverage;
        BigDecimal price;
        BigDecimal size;
        BigDecimal pnl;
        
        @JsonProperty("pnl_percent")
        BigDecimal pnlPercent;
    }
    
    /**
     * DTO for scaled position actions (extend/reduce).
     * Matches frontend expectations: { symbol, scale_percent, reason }
     */
    @Value
    @Builder
    public static class ScaledPositionAction {
        String symbol;
        
        @JsonProperty("scale_percent")
        int scalePercent;
        
        BigDecimal price;
        BigDecimal size;
        BigDecimal pnl;
        String reason;
    }
}
