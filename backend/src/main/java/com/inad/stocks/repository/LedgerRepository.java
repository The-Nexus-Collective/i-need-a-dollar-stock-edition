package com.inad.stocks.repository;

import com.inad.stocks.entity.LedgerEntry;
import com.inad.stocks.entity.enums.AccountType;
import com.inad.stocks.entity.enums.TransactionType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Repository for accounting ledger entries.
 */
@Repository
public interface LedgerRepository extends JpaRepository<LedgerEntry, Long> {
    
    /**
     * Find all entries for a specific transaction.
     */
    List<LedgerEntry> findByTransactionIdOrderByIdAsc(UUID transactionId);
    
    /**
     * Find all entries for a specific position.
     */
    List<LedgerEntry> findByPositionIdOrderByTimestampAsc(String positionId);
    
    /**
     * Find all entries for a specific account.
     */
    List<LedgerEntry> findByAccountOrderByTimestampAsc(AccountType account);
    
    /**
     * Find entries within a time range.
     */
    List<LedgerEntry> findByTimestampBetweenOrderByTimestampAsc(Instant from, Instant to);
    
    /**
     * Find recent entries for a specific account.
     */
    List<LedgerEntry> findTop100ByAccountOrderByTimestampDesc(AccountType account);
    
    /**
     * Calculate total debits for an account.
     */
    @Query("SELECT COALESCE(SUM(e.debit), 0) FROM LedgerEntry e WHERE e.account = :account")
    BigDecimal sumDebitsByAccount(@Param("account") AccountType account);
    
    /**
     * Calculate total credits for an account.
     */
    @Query("SELECT COALESCE(SUM(e.credit), 0) FROM LedgerEntry e WHERE e.account = :account")
    BigDecimal sumCreditsByAccount(@Param("account") AccountType account);
    
    /**
     * Calculate account balance (debits - credits for assets, credits - debits for equity).
     */
    @Query("SELECT COALESCE(SUM(e.debit), 0) - COALESCE(SUM(e.credit), 0) FROM LedgerEntry e WHERE e.account = :account")
    BigDecimal calculateNetBalance(@Param("account") AccountType account);
    
    /**
     * Calculate total debits across all accounts.
     */
    @Query("SELECT COALESCE(SUM(e.debit), 0) FROM LedgerEntry e")
    BigDecimal sumAllDebits();
    
    /**
     * Calculate total credits across all accounts.
     */
    @Query("SELECT COALESCE(SUM(e.credit), 0) FROM LedgerEntry e")
    BigDecimal sumAllCredits();
    
    /**
     * Check if a transaction is balanced (sum of debits = sum of credits).
     */
    @Query("SELECT COALESCE(SUM(e.debit), 0) - COALESCE(SUM(e.credit), 0) FROM LedgerEntry e WHERE e.transactionId = :txId")
    BigDecimal calculateTransactionImbalance(@Param("txId") UUID transactionId);
    
    /**
     * Get the most recent entry for an account.
     */
    LedgerEntry findFirstByAccountOrderByTimestampDesc(AccountType account);
    
    /**
     * Count entries by transaction type.
     */
    long countByTransactionType(TransactionType transactionType);
    
    /**
     * Delete all entries (for reset).
     */
    @Query("DELETE FROM LedgerEntry e")
    void deleteAllEntries();
    
    /**
     * Get total trading costs.
     */
    @Query("SELECT COALESCE(SUM(e.debit), 0) FROM LedgerEntry e WHERE e.account = 'TRADING_COSTS'")
    BigDecimal sumTradingCosts();
    
    /**
     * Get total realized PnL.
     */
    @Query("SELECT COALESCE(SUM(e.credit), 0) - COALESCE(SUM(e.debit), 0) FROM LedgerEntry e WHERE e.account = 'REALIZED_PNL'")
    BigDecimal sumRealizedPnl();
    
    /**
     * Get distinct transaction IDs ordered by timestamp descending.
     */
    @Query("SELECT DISTINCT e.transactionId FROM LedgerEntry e ORDER BY MAX(e.timestamp) DESC")
    List<UUID> findDistinctTransactionIdsOrderByTimestampDesc();
    
    /**
     * Find entries by transaction types (for filtering).
     */
    List<LedgerEntry> findByTransactionTypeInOrderByTimestampDesc(List<TransactionType> types);
    
    /**
     * Get all entries ordered by timestamp descending for transaction building.
     */
    @Query("SELECT e FROM LedgerEntry e WHERE e.transactionType IN :types ORDER BY e.timestamp DESC")
    List<LedgerEntry> findByTransactionTypesOrderByTimestampDesc(@Param("types") List<TransactionType> types);
    
    /**
     * Find entries by transaction ID.
     */
    List<LedgerEntry> findByTransactionId(UUID transactionId);
}

