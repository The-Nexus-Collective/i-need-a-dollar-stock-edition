package com.trading.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Portfolio snapshot entity for equity curve
 * Maps to portfolio_snapshots table
 */
@Entity
@Table(name = "portfolio_snapshots")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PortfolioSnapshot {

    @Id
    @Builder.Default
    private Instant timestamp = Instant.now();

    @Column(name = "total_equity", nullable = false, precision = 20, scale = 8)
    private BigDecimal totalEquity;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal cash;

    @Column(name = "positions_value", nullable = false, precision = 20, scale = 8)
    private BigDecimal positionsValue;

    @Column(name = "unrealized_pnl", nullable = false, precision = 20, scale = 8)
    private BigDecimal unrealizedPnl;

    @Column(name = "realized_pnl", nullable = false, precision = 20, scale = 8)
    private BigDecimal realizedPnl;

    @Column(name = "daily_pnl", precision = 20, scale = 8)
    private BigDecimal dailyPnl;

    @Column(name = "daily_pnl_percent", precision = 8, scale = 4)
    private BigDecimal dailyPnlPercent;

    @Column(name = "var_95", precision = 20, scale = 8)
    private BigDecimal var95;

    @Column(name = "max_drawdown", precision = 8, scale = 4)
    private BigDecimal maxDrawdown;

    @Column(name = "win_rate", precision = 5, scale = 2)
    private BigDecimal winRate;

    @Column(name = "total_trades")
    @Builder.Default
    private Integer totalTrades = 0;

    @Column(name = "winning_trades")
    @Builder.Default
    private Integer winningTrades = 0;

    @Column(name = "losing_trades")
    @Builder.Default
    private Integer losingTrades = 0;
}

