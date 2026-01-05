package com.inad.stocks.entity.enums;

/**
 * Account types for double-entry bookkeeping.
 * 
 * Asset accounts increase with debits, decrease with credits.
 * Equity accounts increase with credits, decrease with debits.
 * Expense accounts increase with debits (reduce equity).
 */
public enum AccountType {
    /**
     * Available cash/capital for trading.
     * Asset account: Debit to increase, Credit to decrease.
     */
    CASH,
    
    /**
     * Value of open positions at entry cost.
     * Asset account: Debit when opening, Credit when closing.
     */
    POSITIONS,
    
    /**
     * Initial starting capital (constant reference).
     * Equity account: Credit to establish.
     */
    STARTING_CAPITAL,
    
    /**
     * Cumulative realized profit/loss from closed trades.
     * Equity account: Credit for profits, Debit for losses.
     */
    REALIZED_PNL,
    
    /**
     * Trading costs (fees, commissions).
     * Expense account: Debit to increase (reduces equity).
     */
    TRADING_COSTS,
    
    /**
     * Margin used for leveraged positions.
     * Asset account tracking margin collateral.
     */
    MARGIN_USED,
    
    /**
     * Leverage change tracking (for crypto compatibility).
     */
    LEVERAGE_CHANGE;
    
    /**
     * Check if this is an asset account.
     * Asset accounts: balance = debits - credits
     */
    public boolean isAsset() {
        return this == CASH || this == POSITIONS;
    }
    
    /**
     * Check if this is an equity account.
     * Equity accounts: balance = credits - debits
     */
    public boolean isEquity() {
        return this == STARTING_CAPITAL || this == REALIZED_PNL;
    }
    
    /**
     * Check if this is an expense account.
     * Expense accounts reduce equity: balance = debits
     */
    public boolean isExpense() {
        return this == TRADING_COSTS;
    }
}

