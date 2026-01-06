package com.inad.stocks.dto;

import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;

/**
 * Information about an opened position for logbook.
 */
@Data
@Builder
public class OpenedPositionInfo {
    private String symbol;
    private String direction;
    private BigDecimal entryPrice;
    private BigDecimal sizeUsd;
    private int conviction;
    private String reason;
}

