package com.trading.service;

import com.trading.entity.Position;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Calculator for Binance-style margin and liquidation calculations.
 * 
 * Implements correct formulas for:
 * - Initial Margin = Notional / Leverage
 * - Liquidation Price with Maintenance Margin Rate (MMR)
 * - Max leverage based on notional size brackets
 */
@Slf4j
@Service
public class MarginCalculator {
    
    // Binance-style brackets for max leverage (simplified)
    // Real Binance has more granular brackets per symbol
    private static final BigDecimal BRACKET_1_NOTIONAL = new BigDecimal("50000");
    private static final BigDecimal BRACKET_2_NOTIONAL = new BigDecimal("250000");
    private static final BigDecimal BRACKET_3_NOTIONAL = new BigDecimal("1000000");
    private static final BigDecimal BRACKET_4_NOTIONAL = new BigDecimal("5000000");
    
    private static final int BRACKET_1_MAX_LEVERAGE = 125;
    private static final int BRACKET_2_MAX_LEVERAGE = 100;
    private static final int BRACKET_3_MAX_LEVERAGE = 50;
    private static final int BRACKET_4_MAX_LEVERAGE = 20;
    private static final int BRACKET_5_MAX_LEVERAGE = 10;
    
    // Default Maintenance Margin Rates by bracket
    private static final BigDecimal MMR_BRACKET_1 = new BigDecimal("0.004");  // 0.4%
    private static final BigDecimal MMR_BRACKET_2 = new BigDecimal("0.005");  // 0.5%
    private static final BigDecimal MMR_BRACKET_3 = new BigDecimal("0.01");   // 1.0%
    private static final BigDecimal MMR_BRACKET_4 = new BigDecimal("0.025");  // 2.5%
    
    /**
     * Calculate the liquidation price for a position.
     * 
     * Formula:
     * LONG:  Liq = Entry * (1 - IMR + MMR) = Entry * (1 - 1/leverage + MMR)
     * SHORT: Liq = Entry * (1 + IMR - MMR) = Entry * (1 + 1/leverage - MMR)
     * 
     * Where:
     * - IMR = Initial Margin Rate = 1 / leverage
     * - MMR = Maintenance Margin Rate (from bracket)
     */
    public BigDecimal calculateLiquidationPrice(Position position) {
        if (position.getEntryPrice() == null || position.getLeverage() == null || position.getLeverage() <= 0) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal entryPrice = position.getEntryPrice();
        int leverage = position.getLeverage();
        BigDecimal mmr = position.getMaintMarginRate() != null 
                ? position.getMaintMarginRate() 
                : getMaintMarginRate(position.getSymbol(), position.getSizeUsdt());
        
        // IMR = 1 / leverage
        BigDecimal imr = BigDecimal.ONE.divide(BigDecimal.valueOf(leverage), 8, RoundingMode.HALF_UP);
        
        BigDecimal liquidationPrice;
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            // LONG: Liq = Entry * (1 - IMR + MMR)
            BigDecimal factor = BigDecimal.ONE.subtract(imr).add(mmr);
            liquidationPrice = entryPrice.multiply(factor);
        } else {
            // SHORT: Liq = Entry * (1 + IMR - MMR)
            BigDecimal factor = BigDecimal.ONE.add(imr).subtract(mmr);
            liquidationPrice = entryPrice.multiply(factor);
        }
        
        return liquidationPrice.setScale(8, RoundingMode.HALF_UP);
    }
    
    /**
     * Calculate initial margin for a position.
     * Initial Margin = Notional / Leverage
     */
    public BigDecimal calculateInitialMargin(BigDecimal notional, int leverage) {
        if (notional == null || leverage <= 0) {
            return BigDecimal.ZERO;
        }
        return notional.divide(BigDecimal.valueOf(leverage), 8, RoundingMode.HALF_UP);
    }
    
    /**
     * Get max leverage for a given symbol and notional size.
     * Based on Binance risk limit brackets.
     */
    public int getMaxLeverage(String symbol, BigDecimal notional) {
        if (notional == null) {
            return BRACKET_1_MAX_LEVERAGE;
        }
        
        if (notional.compareTo(BRACKET_1_NOTIONAL) <= 0) {
            return BRACKET_1_MAX_LEVERAGE;
        } else if (notional.compareTo(BRACKET_2_NOTIONAL) <= 0) {
            return BRACKET_2_MAX_LEVERAGE;
        } else if (notional.compareTo(BRACKET_3_NOTIONAL) <= 0) {
            return BRACKET_3_MAX_LEVERAGE;
        } else if (notional.compareTo(BRACKET_4_NOTIONAL) <= 0) {
            return BRACKET_4_MAX_LEVERAGE;
        } else {
            return BRACKET_5_MAX_LEVERAGE;
        }
    }
    
    /**
     * Get maintenance margin rate for a given symbol and notional size.
     */
    public BigDecimal getMaintMarginRate(String symbol, BigDecimal notional) {
        if (notional == null) {
            return MMR_BRACKET_1;
        }
        
        if (notional.compareTo(BRACKET_1_NOTIONAL) <= 0) {
            return MMR_BRACKET_1;
        } else if (notional.compareTo(BRACKET_2_NOTIONAL) <= 0) {
            return MMR_BRACKET_2;
        } else if (notional.compareTo(BRACKET_3_NOTIONAL) <= 0) {
            return MMR_BRACKET_3;
        } else {
            return MMR_BRACKET_4;
        }
    }
    
    /**
     * Calculate margin risk percentage (0-100%).
     * Shows how close the current price is to the liquidation price.
     */
    public BigDecimal calculateMarginRisk(Position position, BigDecimal currentPrice) {
        if (currentPrice == null || position.getLiquidationPrice() == null || 
            position.getLiquidationPrice().compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal entryPrice = position.getEntryPrice();
        BigDecimal liqPrice = position.getLiquidationPrice();
        
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            if (currentPrice.compareTo(entryPrice) >= 0) {
                return BigDecimal.ZERO;
            }
            BigDecimal distanceToLiq = entryPrice.subtract(liqPrice);
            BigDecimal currentLoss = entryPrice.subtract(currentPrice);
            if (distanceToLiq.compareTo(BigDecimal.ZERO) <= 0) {
                return new BigDecimal("100");
            }
            return currentLoss.divide(distanceToLiq, 4, RoundingMode.HALF_UP)
                    .multiply(new BigDecimal("100"))
                    .min(new BigDecimal("100"));
        } else {
            if (currentPrice.compareTo(entryPrice) <= 0) {
                return BigDecimal.ZERO;
            }
            BigDecimal distanceToLiq = liqPrice.subtract(entryPrice);
            BigDecimal currentLoss = currentPrice.subtract(entryPrice);
            if (distanceToLiq.compareTo(BigDecimal.ZERO) <= 0) {
                return new BigDecimal("100");
            }
            return currentLoss.divide(distanceToLiq, 4, RoundingMode.HALF_UP)
                    .multiply(new BigDecimal("100"))
                    .min(new BigDecimal("100"));
        }
    }
    
    /**
     * Validate if a leverage value is valid for a position.
     */
    public boolean isValidLeverage(String symbol, BigDecimal notional, int leverage) {
        if (leverage < 1) {
            return false;
        }
        int maxLeverage = getMaxLeverage(symbol, notional);
        return leverage <= maxLeverage;
    }
}

