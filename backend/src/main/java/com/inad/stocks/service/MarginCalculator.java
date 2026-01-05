package com.inad.stocks.service;

import com.inad.stocks.entity.Position;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Calculator for stock margin and risk calculations.
 * 
 * Stock margin differs significantly from crypto:
 * - Reg T margin: 50% initial margin (2x max leverage)
 * - Maintenance margin: typically 25-30%
 * - No liquidation in crypto sense, but margin calls occur
 * 
 * For this paper trading system, we use simplified margin rules.
 */
@Slf4j
@Service
public class MarginCalculator {
    
    // Stock margin requirements (US Reg T rules)
    private static final BigDecimal INITIAL_MARGIN_RATE = new BigDecimal("0.50");  // 50% initial margin
    private static final BigDecimal MAINTENANCE_MARGIN_RATE = new BigDecimal("0.25");  // 25% maintenance
    private static final int MAX_LEVERAGE = 2;  // 2x max leverage for Reg T margin
    private static final int DAY_TRADE_LEVERAGE = 4;  // 4x for pattern day traders
    
    /**
     * Calculate the margin call price for a position.
     * 
     * For stocks, a margin call occurs when equity falls below maintenance margin.
     * This is not the same as crypto liquidation, but serves a similar purpose.
     * 
     * Formula for LONG:
     * Margin Call Price = Entry Price × (1 - Maintenance Margin Rate)
     * 
     * For stocks we don't have actual liquidation, so this represents
     * the price at which a margin call would be issued.
     */
    public BigDecimal calculateLiquidationPrice(Position position) {
        if (position.getEntryPrice() == null) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal entryPrice = position.getEntryPrice();
        
        // For stocks, we use a simplified margin call price
        // This represents ~25% loss from entry (maintenance margin)
        BigDecimal marginCallPrice;
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            // LONG: Price can drop by maintenance margin before call
            marginCallPrice = entryPrice.multiply(BigDecimal.ONE.subtract(MAINTENANCE_MARGIN_RATE));
        } else {
            // SHORT: Price can rise by maintenance margin before call
            marginCallPrice = entryPrice.multiply(BigDecimal.ONE.add(MAINTENANCE_MARGIN_RATE));
        }
        
        return marginCallPrice.setScale(8, RoundingMode.HALF_UP);
    }
    
    /**
     * Calculate initial margin for a position.
     * For stocks with Reg T: Initial Margin = Notional × 50%
     */
    public BigDecimal calculateInitialMargin(BigDecimal notional, int leverage) {
        if (notional == null) {
            return BigDecimal.ZERO;
        }
        // For stocks, we require 50% margin for margin accounts
        // Leverage parameter is ignored for actual margin calculation
        return notional.multiply(INITIAL_MARGIN_RATE).setScale(8, RoundingMode.HALF_UP);
    }
    
    /**
     * Get max leverage for stocks.
     * Standard margin accounts: 2x
     * Pattern day traders: 4x intraday
     */
    public int getMaxLeverage(String symbol, BigDecimal notional) {
        // For paper trading, allow day trading leverage
        return DAY_TRADE_LEVERAGE;
    }
    
    /**
     * Get maintenance margin rate for stocks.
     * Standard rate is 25% for most stocks.
     */
    public BigDecimal getMaintMarginRate(String symbol, BigDecimal notional) {
        return MAINTENANCE_MARGIN_RATE;
    }
    
    /**
     * Calculate margin risk percentage (0-100%).
     * Shows how close the current price is to a margin call.
     */
    public BigDecimal calculateMarginRisk(Position position, BigDecimal currentPrice) {
        if (currentPrice == null || position.getEntryPrice() == null) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal entryPrice = position.getEntryPrice();
        BigDecimal marginCallPrice = calculateLiquidationPrice(position);
        
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            // No risk if price is above entry
            if (currentPrice.compareTo(entryPrice) >= 0) {
                return BigDecimal.ZERO;
            }
            // Calculate how far we are towards margin call
            BigDecimal totalDistance = entryPrice.subtract(marginCallPrice);
            BigDecimal currentLoss = entryPrice.subtract(currentPrice);
            if (totalDistance.compareTo(BigDecimal.ZERO) <= 0) {
                return new BigDecimal("100");
            }
            return currentLoss.divide(totalDistance, 4, RoundingMode.HALF_UP)
                    .multiply(new BigDecimal("100"))
                    .min(new BigDecimal("100"))
                    .max(BigDecimal.ZERO);
        } else {
            // SHORT: No risk if price is below entry
            if (currentPrice.compareTo(entryPrice) <= 0) {
                return BigDecimal.ZERO;
            }
            BigDecimal totalDistance = marginCallPrice.subtract(entryPrice);
            BigDecimal currentLoss = currentPrice.subtract(entryPrice);
            if (totalDistance.compareTo(BigDecimal.ZERO) <= 0) {
                return new BigDecimal("100");
            }
            return currentLoss.divide(totalDistance, 4, RoundingMode.HALF_UP)
                    .multiply(new BigDecimal("100"))
                    .min(new BigDecimal("100"))
                    .max(BigDecimal.ZERO);
        }
    }
    
    /**
     * Validate if a leverage value is valid for stock trading.
     */
    public boolean isValidLeverage(String symbol, BigDecimal notional, int leverage) {
        if (leverage < 1) {
            return false;
        }
        return leverage <= DAY_TRADE_LEVERAGE;
    }
}
