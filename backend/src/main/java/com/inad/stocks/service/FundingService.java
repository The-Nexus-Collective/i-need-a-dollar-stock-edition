package com.inad.stocks.service;

import com.inad.stocks.entity.Position;
import com.inad.stocks.repository.PositionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * Funding service stub for stock trading.
 * 
 * Unlike crypto perpetual futures, stocks do not have funding rates.
 * This service is kept as a stub to maintain compatibility with the
 * trading scheduler, but all operations are no-ops.
 * 
 * For stocks, relevant costs are:
 * - Commission fees (handled by FeeService)
 * - Dividend payments (not yet implemented)
 * - Margin interest (not yet implemented)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FundingService {
    
    private final PositionRepository positionRepository;
    
    /**
     * Funding rates don't apply to stocks.
     * Always returns zero.
     */
    public BigDecimal getFundingRate(String symbol) {
        return BigDecimal.ZERO;
    }
    
    /**
     * Funding fees don't apply to stocks.
     * Always returns zero.
     */
    public BigDecimal calculateFundingFee(Position position, BigDecimal fundingRate) {
        return BigDecimal.ZERO;
    }
    
    /**
     * No funding payments to process for stocks.
     * Returns an empty result.
     */
    public FundingResult processFundingPayments() {
        log.debug("Funding payments not applicable for stock trading - skipping");
        return new FundingResult(0, 0, BigDecimal.ZERO, BigDecimal.ZERO);
    }
    
    /**
     * Funding costs don't apply to stocks.
     * Always returns zero.
     */
    public BigDecimal estimateDailyFundingCost(Position position) {
        return BigDecimal.ZERO;
    }
    
    /**
     * Result of funding payment processing.
     */
    public record FundingResult(
        int positionsProcessed,
        int positionsFailed,
        BigDecimal totalPaid,
        BigDecimal totalReceived
    ) {
        public BigDecimal netFunding() {
            return totalReceived.subtract(totalPaid);
        }
    }
}
