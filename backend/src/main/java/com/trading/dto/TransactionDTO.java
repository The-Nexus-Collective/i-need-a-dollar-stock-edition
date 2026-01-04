package com.trading.dto;

import com.trading.entity.enums.TransactionType;
import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * DTO representing a trading transaction for the History page.
 * Aggregates ledger entries into a user-friendly transaction view.
 */
@Data
@Builder
public class TransactionDTO {
    
    /**
     * Unique transaction ID (groups related ledger entries).
     */
    private UUID transactionId;
    
    /**
     * When the transaction occurred.
     */
    private Instant timestamp;
    
    /**
     * Type of transaction: OPEN, CLOSE, EXTEND, REDUCE, RESET.
     */
    private TransactionType transactionType;
    
    /**
     * Human-readable transaction type.
     */
    private String transactionTypeDisplay;
    
    /**
     * Position ID this transaction relates to.
     */
    private String positionId;
    
    /**
     * Trading symbol (e.g., BTCUSDT).
     */
    private String symbol;
    
    /**
     * Trade direction: LONG or SHORT.
     */
    private String direction;
    
    /**
     * Execution price.
     */
    private BigDecimal price;
    
    /**
     * Quantity traded.
     */
    private BigDecimal quantity;
    
    /**
     * Size in USDT (notional value).
     */
    private BigDecimal sizeUsdt;
    
    /**
     * Leverage used.
     */
    private Integer leverage;
    
    /**
     * Conviction score (0-100).
     */
    private Integer conviction;
    
    /**
     * Reasoning for the trade.
     */
    private String reason;
    
    // ========== Cost Breakdown ==========
    
    /**
     * Trading fee.
     */
    private BigDecimal fee;
    
    /**
     * Spread cost.
     */
    private BigDecimal spread;
    
    /**
     * Slippage cost.
     */
    private BigDecimal slippage;
    
    /**
     * Total costs (fee + spread + slippage).
     */
    private BigDecimal totalCosts;
    
    // ========== PnL (for CLOSE/REDUCE) ==========
    
    /**
     * Gross PnL before costs.
     */
    private BigDecimal grossPnl;
    
    /**
     * Net PnL after costs.
     */
    private BigDecimal netPnl;
    
    /**
     * PnL as percentage of position size.
     */
    private BigDecimal pnlPercent;
    
    // ========== Position State (for EXTEND/REDUCE) ==========
    
    /**
     * Position size before this transaction.
     */
    private BigDecimal positionSizeBefore;
    
    /**
     * Position size after this transaction.
     */
    private BigDecimal positionSizeAfter;
    
    /**
     * Average entry price before this transaction.
     */
    private BigDecimal avgEntryBefore;
    
    /**
     * Average entry price after this transaction.
     */
    private BigDecimal avgEntryAfter;
    
    // ========== Expandable Ledger Detail ==========
    
    /**
     * Individual ledger entries for this transaction.
     * Populated when expanded view is requested.
     */
    private List<LedgerEntryDTO> ledgerEntries;
    
    /**
     * Number of ledger entries (for UI display before expansion).
     */
    private Integer ledgerEntryCount;
    
    /**
     * Get display-friendly transaction type.
     */
    public String getTransactionTypeDisplay() {
        if (transactionTypeDisplay != null) {
            return transactionTypeDisplay;
        }
        return transactionType != null ? transactionType.name() : "UNKNOWN";
    }
}

