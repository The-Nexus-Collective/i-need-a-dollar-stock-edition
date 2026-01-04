package com.trading.dto;

import lombok.Data;
import lombok.Builder;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

/**
 * Equity data for WebSocket streaming
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class EquityData {
    
    private String timestamp;
    
    @JsonProperty("total_equity")
    private BigDecimal totalEquity;
    
    private BigDecimal cash;
    
    @JsonProperty("positions_value")
    private BigDecimal positionsValue;
    
    @JsonProperty("unrealized_pnl")
    private BigDecimal unrealizedPnl;
    
    @JsonProperty("position_details")
    private List<PositionDetail> positionDetails;
    
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PositionDetail {
        private String symbol;
        private String direction;
        
        @JsonProperty("entry_price")
        private BigDecimal entryPrice;
        
        @JsonProperty("current_price")
        private BigDecimal currentPrice;
        
        @JsonProperty("size_usdt")
        private BigDecimal sizeUsdt;
        
        @JsonProperty("unrealized_pnl")
        private BigDecimal unrealizedPnl;
        
        @JsonProperty("pnl_percent")
        private BigDecimal pnlPercent;
    }
}

