package com.trading.dto;

import lombok.Data;
import lombok.Builder;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Position DTO for API responses
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PositionDTO {
    
    private String id;
    private String symbol;
    private String direction;
    
    @JsonProperty("entry_price")
    private BigDecimal entryPrice;
    
    private BigDecimal quantity;
    
    @JsonProperty("size_usdt")
    private BigDecimal sizeUsdt;
    
    private Integer leverage;
    
    @JsonProperty("stop_loss_price")
    private BigDecimal stopLossPrice;
    
    @JsonProperty("take_profit_price")
    private BigDecimal takeProfitPrice;
    
    private String status;
    
    @JsonProperty("entry_time")
    private Instant entryTime;
    
    @JsonProperty("exit_time")
    private Instant exitTime;
    
    @JsonProperty("exit_price")
    private BigDecimal exitPrice;
    
    @JsonProperty("realized_pnl")
    private BigDecimal realizedPnl;
    
    @JsonProperty("unrealized_pnl")
    private BigDecimal unrealizedPnl;
    
    @JsonProperty("pnl_percent")
    private BigDecimal pnlPercent;
    
    private BigDecimal conviction;
    private String reasoning;
    
    @JsonProperty("current_price")
    private BigDecimal currentPrice;
    
    @JsonProperty("liquidation_price")
    private BigDecimal liquidationPrice;
}

