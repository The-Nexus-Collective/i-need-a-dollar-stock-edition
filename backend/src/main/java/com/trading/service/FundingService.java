package com.trading.service;

import com.trading.entity.Position;
import com.trading.integration.binance.BinanceClient;
import com.trading.repository.PositionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

/**
 * Service for handling Binance-style funding fees.
 * 
 * Funding is exchanged every 8 hours (00:00, 08:00, 16:00 UTC) between
 * long and short position holders based on the funding rate.
 * 
 * Positive funding rate: Longs pay shorts
 * Negative funding rate: Shorts pay longs
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FundingService {
    
    private final BinanceClient binanceClient;
    private final PositionRepository positionRepository;
    private final AccountingService accountingService;
    
    // Default funding rate if API call fails (typical neutral rate)
    private static final BigDecimal DEFAULT_FUNDING_RATE = new BigDecimal("0.0001"); // 0.01%
    
    /**
     * Fetch the current funding rate for a symbol from Binance.
     * 
     * Typical rates range from -0.1% to +0.1% per 8 hours.
     * Positive = longs pay shorts, Negative = shorts pay longs.
     */
    public BigDecimal getFundingRate(String symbol) {
        try {
            BigDecimal rate = binanceClient.getFundingRate(symbol);
            if (rate != null && rate.compareTo(BigDecimal.ZERO) != 0) {
                return rate;
            }
        } catch (Exception e) {
            log.warn("Failed to fetch funding rate for {}: {}", symbol, e.getMessage());
        }
        return DEFAULT_FUNDING_RATE;
    }
    
    /**
     * Calculate the funding fee for a position.
     * 
     * Formula: Funding Fee = Notional × Funding Rate
     * 
     * For LONG positions:
     * - Positive rate = payment (cost)
     * - Negative rate = receipt (income)
     * 
     * For SHORT positions:
     * - Positive rate = receipt (income)
     * - Negative rate = payment (cost)
     * 
     * @return Positive value = payment (cost), Negative value = receipt (income)
     */
    public BigDecimal calculateFundingFee(Position position, BigDecimal fundingRate) {
        if (position == null || position.getSizeUsdt() == null || fundingRate == null) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal notional = position.getSizeUsdt();
        BigDecimal fee = notional.multiply(fundingRate).setScale(8, RoundingMode.HALF_UP);
        
        // LONG pays when rate is positive, receives when negative
        // SHORT receives when rate is positive, pays when negative
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            return fee;  // Positive rate = payment for longs
        } else {
            return fee.negate();  // Positive rate = receipt for shorts
        }
    }
    
    /**
     * Process funding payments for all open positions.
     * Should be called at funding times: 00:00, 08:00, 16:00 UTC
     */
    @Transactional
    public FundingResult processFundingPayments() {
        log.info("Processing funding payments...");
        
        List<Position> openPositions = positionRepository.findOpenPositions();
        
        int processed = 0;
        int failed = 0;
        BigDecimal totalPaid = BigDecimal.ZERO;
        BigDecimal totalReceived = BigDecimal.ZERO;
        
        for (Position position : openPositions) {
            try {
                BigDecimal fundingRate = getFundingRate(position.getSymbol());
                BigDecimal fundingFee = calculateFundingFee(position, fundingRate);
                
                // Record in accounting ledger
                accountingService.recordFundingPayment(
                    position.getId(),
                    position.getSymbol(),
                    fundingFee,
                    fundingRate
                );
                
                if (fundingFee.compareTo(BigDecimal.ZERO) > 0) {
                    totalPaid = totalPaid.add(fundingFee);
                } else {
                    totalReceived = totalReceived.add(fundingFee.abs());
                }
                
                processed++;
                
                log.debug("Funding {}: {} @ rate {} = {} USDT", 
                    position.getSymbol(), 
                    position.getDirection(), 
                    fundingRate, 
                    fundingFee);
                    
            } catch (Exception e) {
                log.error("Failed to process funding for position {}: {}", 
                    position.getId(), e.getMessage());
                failed++;
            }
        }
        
        log.info("Funding processed: {} positions, paid {} USDT, received {} USDT, {} failed",
            processed, totalPaid, totalReceived, failed);
        
        return new FundingResult(processed, failed, totalPaid, totalReceived);
    }
    
    /**
     * Calculate estimated daily funding cost for a position.
     * Assumes 3 funding periods per day and uses current funding rate.
     */
    public BigDecimal estimateDailyFundingCost(Position position) {
        BigDecimal fundingRate = getFundingRate(position.getSymbol());
        BigDecimal perPeriodFee = calculateFundingFee(position, fundingRate);
        return perPeriodFee.multiply(BigDecimal.valueOf(3)); // 3 periods per day
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

