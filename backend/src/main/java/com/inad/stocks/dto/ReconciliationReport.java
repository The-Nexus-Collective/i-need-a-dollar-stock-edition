package com.inad.stocks.dto;

import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Report from accounting reconciliation.
 */
@Data
@Builder
public class ReconciliationReport {
    
    /**
     * Whether the books are balanced.
     */
    private boolean balanced;
    
    /**
     * Timestamp of this reconciliation.
     */
    private Instant timestamp;
    
    /**
     * Total debits across all accounts.
     */
    private BigDecimal totalDebits;
    
    /**
     * Total credits across all accounts.
     */
    private BigDecimal totalCredits;
    
    /**
     * Imbalance amount (should be zero if balanced).
     */
    private BigDecimal imbalance;
    
    /**
     * Individual account balances.
     */
    private Map<String, BigDecimal> accountBalances;
    
    /**
     * Calculated total equity from accounts.
     */
    private BigDecimal calculatedEquity;
    
    /**
     * Expected equity (starting capital + realized PnL - costs).
     */
    private BigDecimal expectedEquity;
    
    /**
     * Any discrepancies found.
     */
    private List<String> discrepancies;
    
    /**
     * Total number of ledger entries.
     */
    private long totalEntries;
    
    /**
     * Number of transactions.
     */
    private long totalTransactions;
}

