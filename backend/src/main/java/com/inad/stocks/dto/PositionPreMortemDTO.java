package com.inad.stocks.dto;

import com.inad.stocks.service.PreMortemCheckerService.PreMortemStatus;
import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

/**
 * DTO for position with Pre-Mortem status information.
 */
@Data
@Builder
public class PositionPreMortemDTO {
    private String positionId;
    private String symbol;
    private String direction;
    private BigDecimal entryPrice;
    private BigDecimal currentPrice;
    private BigDecimal currentPnlPercent;
    private int holdHours;
    private String preMortem;
    private String bullCase;
    private String bearCase;
    private Integer expectedHoldHoursMin;
    private Integer expectedHoldHoursMax;
    private PreMortemStatus status;
    private List<String> signals;
}

