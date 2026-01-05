package com.inad.stocks.integration.broker;

import java.math.BigDecimal;
import java.util.Map;

/**
 * Interface for stock broker operations.
 * 
 * This abstraction allows for different implementations:
 * - YahooFinanceClient: Mock broker using free Yahoo Finance API for prices
 * - CapTraderClient: Future implementation for real trading via IBKR API
 */
public interface StockBrokerClient {
    
    /**
     * Get the current price for a stock symbol.
     * 
     * @param symbol Stock symbol (e.g., "AAPL", "MSFT", "RTX")
     * @return Current market price, or null if unavailable
     */
    BigDecimal getPrice(String symbol);
    
    /**
     * Get current prices for multiple stock symbols.
     * 
     * @param symbols Array of stock symbols
     * @return Map of symbol to current price
     */
    Map<String, BigDecimal> getPrices(String... symbols);
    
    /**
     * Open a new position (paper trading simulation).
     * 
     * @param symbol Stock symbol
     * @param side "BUY" or "SELL" (for short positions)
     * @param amount USD amount to invest
     * @return Trade result with execution details
     */
    TradeResult openPosition(String symbol, String side, BigDecimal amount);
    
    /**
     * Close an existing position (paper trading simulation).
     * 
     * @param symbol Stock symbol
     * @param side "SELL" for closing longs, "BUY" for covering shorts
     * @param quantity Number of shares to close
     * @param entryPrice Original entry price for P&L calculation
     * @return Trade result with execution details
     */
    TradeResult closePosition(String symbol, String side, BigDecimal quantity, BigDecimal entryPrice);
    
    /**
     * Check if the broker connection is healthy.
     * 
     * @return true if connected and operational
     */
    boolean isConnected();
    
    /**
     * Get all cached prices (for debugging).
     * 
     * @return Map of all cached symbol prices
     */
    default Map<String, BigDecimal> getAllCachedPrices() {
        return Map.of();
    }
    
    /**
     * Result of a trade execution.
     */
    record TradeResult(
        boolean success,
        String positionId,
        String symbol,
        String side,
        BigDecimal executedPrice,
        BigDecimal quantity,
        BigDecimal totalValue,
        BigDecimal fee,
        String message
    ) {
        public static TradeResult success(String positionId, String symbol, String side,
                                         BigDecimal price, BigDecimal qty, BigDecimal fee) {
            return new TradeResult(true, positionId, symbol, side, price, qty,
                    price.multiply(qty), fee, "Order executed successfully");
        }
        
        public static TradeResult failure(String symbol, String message) {
            return new TradeResult(false, null, symbol, null, null, null, null, null, message);
        }
        
        // Alias methods for backward compatibility
        public boolean isSuccess() { return success; }
        public String getError() { return message; }
        public BigDecimal getPrice() { return executedPrice; }
        public BigDecimal getQuantity() { return quantity; }
        public BigDecimal getFee() { return fee; }
        public BigDecimal getSpread() { return BigDecimal.ZERO; }  // Not tracked separately for stocks
        public BigDecimal getSlippage() { return BigDecimal.ZERO; } // Included in execution price
    }
}

