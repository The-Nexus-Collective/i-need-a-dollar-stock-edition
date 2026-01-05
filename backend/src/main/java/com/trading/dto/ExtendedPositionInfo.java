package com.trading.dto;

import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;

/**
 * Information about an extended position for logbook.
 */
@Data
@Builder
public class ExtendedPositionInfo {
    private String symbol;
    private int scalePercent;
    private BigDecimal addedSize;
    private BigDecimal price;
    private String reason;
}

