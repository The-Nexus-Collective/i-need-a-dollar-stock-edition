package com.trading.entity.enums;

/**
 * Types of accounting transactions in the ledger.
 */
public enum TransactionType {
    /**
     * Opening a new position - debits POSITIONS, credits CASH
     */
    OPEN,
    
    /**
     * Closing an existing position - credits POSITIONS, debits CASH, records PnL
     */
    CLOSE,
    
    /**
     * Extending an existing position - additional entry
     */
    EXTEND,
    
    /**
     * Reducing an existing position - partial close
     */
    REDUCE,
    
    /**
     * Trading fee expense
     */
    FEE,
    
    /**
     * Spread cost expense
     */
    SPREAD,
    
    /**
     * Slippage cost expense
     */
    SLIPPAGE,
    
    /**
     * System reset - clears all positions and resets capital
     */
    RESET,
    
    /**
     * Manual adjustment for corrections
     */
    ADJUSTMENT,
    
    /**
     * Initial capital deposit
     */
    DEPOSIT,
    
    /**
     * Forced liquidation due to margin call - position hit liquidation price
     */
    MARGIN_CALL
}

