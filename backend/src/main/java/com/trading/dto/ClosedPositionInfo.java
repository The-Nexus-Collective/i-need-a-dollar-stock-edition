package com.trading.dto;

import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;

/**
 * Information about a closed position for logbook.
 */
@Data
@Builder
public class ClosedPositionInfo {
    private String symbol;
    private String direction;
    private BigDecimal entryPrice;
    private BigDecimal exitPrice;
    private BigDecimal pnl;
    private BigDecimal pnlPercent;
    private String reason;
}

