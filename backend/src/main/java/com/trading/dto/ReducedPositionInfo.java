package com.trading.dto;

import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;

/**
 * Information about a reduced position for logbook.
 */
@Data
@Builder
public class ReducedPositionInfo {
    private String symbol;
    private int scalePercent;
    private BigDecimal reducedSize;
    private BigDecimal price;
    private BigDecimal partialPnl;
    private String reason;
}

