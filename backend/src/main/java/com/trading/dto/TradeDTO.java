package com.trading.dto;

import lombok.Data;
import lombok.Builder;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Trade DTO for API responses
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TradeDTO {
    
    private String id;
    
    @JsonProperty("position_id")
    private String positionId;
    
    private String symbol;
    private String direction;
    
    @JsonProperty("entry_price")
    private BigDecimal entryPrice;
    
    @JsonProperty("exit_price")
    private BigDecimal exitPrice;
    
    private BigDecimal quantity;
    
    @JsonProperty("size_usdt")
    private BigDecimal sizeUsdt;
    
    private Integer leverage;
    
    @JsonProperty("pnl_usdt")
    private BigDecimal pnlUsdt;
    
    @JsonProperty("pnl_percent")
    private BigDecimal pnlPercent;
    
    @JsonProperty("entry_time")
    private Instant entryTime;
    
    @JsonProperty("exit_time")
    private Instant exitTime;
    
    @JsonProperty("duration_seconds")
    private Integer durationSeconds;
    
    @JsonProperty("exit_reason")
    private String exitReason;
    
    private BigDecimal conviction;
    private String reasoning;
    
    @JsonProperty("total_fees")
    private BigDecimal totalFees;
}

