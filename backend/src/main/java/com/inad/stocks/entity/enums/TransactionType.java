package com.inad.stocks.entity.enums;

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
     * Trading fee/commission expense
     */
    FEE,
    
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
     * Dividend received from stock position
     */
    DIVIDEND,
    
    /**
     * Funding payment (crypto-style, kept for compatibility)
     */
    FUNDING,
    
    /**
     * Margin call - forced liquidation
     */
    MARGIN_CALL,
    
    /**
     * Leverage change (crypto-style, kept for compatibility)
     */
    LEVERAGE_CHANGE
}

