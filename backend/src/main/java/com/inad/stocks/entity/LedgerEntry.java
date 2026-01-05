package com.inad.stocks.entity;

import com.inad.stocks.entity.enums.AccountType;
import com.inad.stocks.entity.enums.TransactionType;
import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Immutable ledger entry for double-entry accounting.
 * Each financial transaction creates multiple entries that must balance.
 */
@Entity
@Table(name = "accounting_ledger")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class LedgerEntry {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    /**
     * Groups related entries for one logical transaction.
     * All entries with the same transactionId must balance (debits = credits).
     */
    @Column(name = "transaction_id", nullable = false)
    private UUID transactionId;
    
    /**
     * When this entry was recorded.
     */
    @Column(nullable = false)
    private Instant timestamp;
    
    /**
     * Type of transaction (OPEN, CLOSE, FEE, RESET, etc.)
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "transaction_type", nullable = false)
    private TransactionType transactionType;
    
    /**
     * Reference to the position this entry relates to (nullable for non-position transactions).
     */
    @Column(name = "position_id")
    private String positionId;
    
    /**
     * The account being affected (CASH, POSITIONS, REALIZED_PNL, TRADING_COSTS).
     */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private AccountType account;
    
    /**
     * Debit amount (increases assets/expenses).
     */
    @Column(precision = 20, scale = 8)
    @Builder.Default
    private BigDecimal debit = BigDecimal.ZERO;
    
    /**
     * Credit amount (increases equity/liabilities).
     */
    @Column(precision = 20, scale = 8)
    @Builder.Default
    private BigDecimal credit = BigDecimal.ZERO;
    
    /**
     * Running balance for this account after this entry.
     */
    @Column(name = "running_balance", precision = 20, scale = 8)
    private BigDecimal runningBalance;
    
    /**
     * Human-readable description of this entry.
     */
    private String description;
    
    /**
     * Additional metadata as JSON (prices, quantities, symbols, etc.)
     */
    @Column(columnDefinition = "text")
    private String metadata;
    
    /**
     * Get the net effect on this account.
     * For asset/expense accounts: debit increases, credit decreases.
     * For equity accounts: credit increases, debit decreases.
     */
    public BigDecimal getNetEffect() {
        if (account.isAsset() || account.isExpense()) {
            return debit.subtract(credit);
        } else {
            return credit.subtract(debit);
        }
    }
    
    /**
     * Check if this is a debit entry.
     */
    public boolean isDebit() {
        return debit.compareTo(BigDecimal.ZERO) > 0;
    }
    
    /**
     * Check if this is a credit entry.
     */
    public boolean isCredit() {
        return credit.compareTo(BigDecimal.ZERO) > 0;
    }
}

