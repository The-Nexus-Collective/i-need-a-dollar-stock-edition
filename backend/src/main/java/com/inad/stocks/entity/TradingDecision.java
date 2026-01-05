package com.inad.stocks.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Trading decision entity - records AI trading decisions
 * Maps to trading_decisions table
 */
@Entity
@Table(name = "trading_decisions")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TradingDecision {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false, length = 10)
    private String decision;

    @Column(length = 20)
    private String symbol;

    @Column(length = 10)
    private String direction;

    @Column(name = "size_percent", precision = 5, scale = 2)
    private BigDecimal sizePercent;

    @Column(name = "stop_loss_percent", precision = 5, scale = 2)
    private BigDecimal stopLossPercent;

    @Column(name = "take_profit_percent", precision = 5, scale = 2)
    private BigDecimal takeProfitPercent;

    @Column
    private Integer conviction;

    @Column(columnDefinition = "TEXT")
    private String reasoning;

    @Column(name = "available_capital", precision = 20, scale = 2)
    private BigDecimal availableCapital;

    @Column(name = "open_positions_count")
    private Integer openPositionsCount;

    @Column(name = "market_context", columnDefinition = "jsonb")
    @JdbcTypeCode(SqlTypes.JSON)
    private Map<String, Object> marketContext;

    @Column(name = "was_executed")
    @Builder.Default
    private Boolean wasExecuted = false;

    @Column(name = "position_id", length = 32)
    private String positionId;

    @Column(name = "created_at")
    @Builder.Default
    private Instant createdAt = Instant.now();
}

