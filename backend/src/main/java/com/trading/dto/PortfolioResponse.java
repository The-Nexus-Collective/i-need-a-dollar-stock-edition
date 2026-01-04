package com.trading.dto;

import lombok.Data;
import lombok.Builder;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;

/**
 * Portfolio response DTO matching Python API structure
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PortfolioResponse {
    
    @JsonProperty("total_equity")
    private BigDecimal totalEquity;
    
    @JsonProperty("initial_capital")
    private BigDecimal initialCapital;
    
    private BigDecimal cash;
    
    @JsonProperty("positions_value")
    private BigDecimal positionsValue;
    
    @JsonProperty("unrealized_pnl")
    private BigDecimal unrealizedPnl;
    
    @JsonProperty("realized_pnl")
    private BigDecimal realizedPnl;
    
    @JsonProperty("total_pnl")
    private BigDecimal totalPnl;
    
    @JsonProperty("pnl_percent")
    private BigDecimal pnlPercent;
    
    @JsonProperty("open_positions")
    private int openPositions;
    
    @JsonProperty("total_trades")
    private int totalTrades;
    
    @JsonProperty("winning_trades")
    private int winningTrades;
    
    @JsonProperty("losing_trades")
    private int losingTrades;
    
    @JsonProperty("win_rate")
    private BigDecimal winRate;
    
    @JsonProperty("total_volume")
    private BigDecimal totalVolume;
    
    @JsonProperty("total_fees")
    private BigDecimal totalFees;
    
    @JsonProperty("total_spread")
    private BigDecimal totalSpread;
    
    @JsonProperty("total_slippage")
    private BigDecimal totalSlippage;
    
    @JsonProperty("total_trading_costs")
    private BigDecimal totalTradingCosts;
    
    @JsonProperty("var_95")
    private BigDecimal var95;
    
    @JsonProperty("max_drawdown")
    private BigDecimal maxDrawdown;
}

