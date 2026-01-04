package com.trading.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trading.dto.ReconciliationReport;
import com.trading.entity.LedgerEntry;
import com.trading.entity.enums.AccountType;
import com.trading.entity.enums.TransactionType;
import com.trading.repository.LedgerRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.*;

/**
 * Double-entry accounting service.
 * 
 * All financial transactions go through this service to ensure:
 * - Every transaction is balanced (debits = credits)
 * - Complete audit trail
 * - Reconcilable accounts
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AccountingService {
    
    private final LedgerRepository ledgerRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    @Value("${trading.starting-capital:100000}")
    private BigDecimal startingCapital;
    
    // ========== TRANSACTION RECORDING ==========
    
    /**
     * Record opening a new position.
     * 
     * Debits:
     *   - POSITIONS: sizeUsdt (asset increase)
     *   - TRADING_COSTS: totalCosts (expense)
     * 
     * Credits:
     *   - CASH: sizeUsdt + totalCosts (asset decrease)
     */
    @Transactional
    public UUID recordOpenPosition(String positionId, String symbol, BigDecimal sizeUsdt,
                                    BigDecimal fee, BigDecimal spread, BigDecimal slippage,
                                    BigDecimal entryPrice, String direction) {
        UUID txId = UUID.randomUUID();
        Instant now = Instant.now();
        BigDecimal totalCosts = fee.add(spread).add(slippage);
        BigDecimal totalDeducted = sizeUsdt.add(totalCosts);
        
        // Build metadata
        Map<String, Object> metadata = Map.of(
            "symbol", symbol,
            "direction", direction,
            "entryPrice", entryPrice,
            "sizeUsdt", sizeUsdt,
            "fee", fee,
            "spread", spread,
            "slippage", slippage
        );
        String metadataJson = toJson(metadata);
        
        List<LedgerEntry> entries = new ArrayList<>();
        
        // 1. Debit POSITIONS (increase asset)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.OPEN)
                .positionId(positionId)
                .account(AccountType.POSITIONS)
                .debit(sizeUsdt)
                .credit(BigDecimal.ZERO)
                .description("Position opened: " + direction + " " + symbol)
                .metadata(metadataJson)
                .build());
        
        // 2. Debit TRADING_COSTS (expense)
        if (totalCosts.compareTo(BigDecimal.ZERO) > 0) {
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.FEE)
                    .positionId(positionId)
                    .account(AccountType.TRADING_COSTS)
                    .debit(totalCosts)
                    .credit(BigDecimal.ZERO)
                    .description("Entry costs: fee=" + fee + ", spread=" + spread + ", slippage=" + slippage)
                    .metadata(metadataJson)
                    .build());
        }
        
        // 3. Credit CASH (decrease asset)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.OPEN)
                .positionId(positionId)
                .account(AccountType.CASH)
                .debit(BigDecimal.ZERO)
                .credit(totalDeducted)
                .description("Capital deployed for " + symbol)
                .metadata(metadataJson)
                .build());
        
        // Calculate running balances
        calculateRunningBalances(entries);
        
        // Save all entries
        ledgerRepository.saveAll(entries);
        
        log.info("Recorded OPEN position {}: size={}, costs={}, txId={}", 
                positionId, sizeUsdt, totalCosts, txId);
        
        return txId;
    }
    
    /**
     * Record closing a position.
     * 
     * Credits:
     *   - POSITIONS: sizeUsdt (asset decrease - remove position at entry cost)
     *   - REALIZED_PNL: pnl if profit (equity increase)
     * 
     * Debits:
     *   - CASH: sizeUsdt + pnl - exitCosts (asset increase - return capital)
     *   - REALIZED_PNL: |pnl| if loss (equity decrease)
     *   - TRADING_COSTS: exitCosts (expense)
     */
    @Transactional
    public UUID recordClosePosition(String positionId, String symbol, BigDecimal sizeUsdt,
                                     BigDecimal realizedPnl, BigDecimal exitFee,
                                     BigDecimal exitPrice, String closeReason) {
        UUID txId = UUID.randomUUID();
        Instant now = Instant.now();
        BigDecimal cashReturned = sizeUsdt.add(realizedPnl).subtract(exitFee);
        
        // Build metadata
        Map<String, Object> metadata = Map.of(
            "symbol", symbol,
            "exitPrice", exitPrice,
            "sizeUsdt", sizeUsdt,
            "realizedPnl", realizedPnl,
            "exitFee", exitFee,
            "closeReason", closeReason
        );
        String metadataJson = toJson(metadata);
        
        List<LedgerEntry> entries = new ArrayList<>();
        
        // 1. Credit POSITIONS (decrease asset - remove at entry cost)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.CLOSE)
                .positionId(positionId)
                .account(AccountType.POSITIONS)
                .debit(BigDecimal.ZERO)
                .credit(sizeUsdt)
                .description("Position closed: " + symbol + " - " + closeReason)
                .metadata(metadataJson)
                .build());
        
        // 2. Record PnL
        if (realizedPnl.compareTo(BigDecimal.ZERO) >= 0) {
            // Profit: Credit REALIZED_PNL (increase equity)
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.CLOSE)
                    .positionId(positionId)
                    .account(AccountType.REALIZED_PNL)
                    .debit(BigDecimal.ZERO)
                    .credit(realizedPnl)
                    .description("Profit realized: " + symbol)
                    .metadata(metadataJson)
                    .build());
        } else {
            // Loss: Debit REALIZED_PNL (decrease equity)
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.CLOSE)
                    .positionId(positionId)
                    .account(AccountType.REALIZED_PNL)
                    .debit(realizedPnl.abs())
                    .credit(BigDecimal.ZERO)
                    .description("Loss realized: " + symbol)
                    .metadata(metadataJson)
                    .build());
        }
        
        // 3. Debit TRADING_COSTS (expense)
        if (exitFee.compareTo(BigDecimal.ZERO) > 0) {
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.FEE)
                    .positionId(positionId)
                    .account(AccountType.TRADING_COSTS)
                    .debit(exitFee)
                    .credit(BigDecimal.ZERO)
                    .description("Exit fee: " + symbol)
                    .metadata(metadataJson)
                    .build());
        }
        
        // 4. Debit CASH (increase asset - return capital with PnL)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.CLOSE)
                .positionId(positionId)
                .account(AccountType.CASH)
                .debit(cashReturned)
                .credit(BigDecimal.ZERO)
                .description("Capital returned from " + symbol)
                .metadata(metadataJson)
                .build());
        
        // Calculate running balances
        calculateRunningBalances(entries);
        
        // Save all entries
        ledgerRepository.saveAll(entries);
        
        log.info("Recorded CLOSE position {}: pnl={}, cashReturned={}, txId={}", 
                positionId, realizedPnl, cashReturned, txId);
        
        return txId;
    }
    
    /**
     * Record a margin call (forced liquidation).
     * 
     * This is similar to closePosition but uses MARGIN_CALL transaction type
     * and always results in a total loss of the margin (position size).
     * 
     * Credits:
     *   - POSITIONS: sizeUsdt (asset decrease - remove position at entry cost)
     * 
     * Debits:
     *   - REALIZED_PNL: |loss| (equity decrease - the full margin is lost)
     *   - CASH: any remaining value (usually near zero or negative after fees)
     */
    @Transactional
    public UUID recordMarginCall(String positionId, String symbol, BigDecimal sizeUsdt,
                                  BigDecimal realizedPnl, BigDecimal exitPrice) {
        UUID txId = UUID.randomUUID();
        Instant now = Instant.now();
        
        // Cash returned is the remaining value after liquidation (sizeUsdt + realizedPnl)
        // For a margin call, realizedPnl is typically close to -sizeUsdt (100% loss)
        BigDecimal cashReturned = sizeUsdt.add(realizedPnl);
        if (cashReturned.compareTo(BigDecimal.ZERO) < 0) {
            cashReturned = BigDecimal.ZERO; // Can't return negative cash
        }
        
        // Build metadata
        Map<String, Object> metadata = Map.of(
            "symbol", symbol,
            "exitPrice", exitPrice,
            "sizeUsdt", sizeUsdt,
            "realizedPnl", realizedPnl,
            "closeReason", "MARGIN_CALL",
            "marginCallExecuted", true
        );
        String metadataJson = toJson(metadata);
        
        List<LedgerEntry> entries = new ArrayList<>();
        
        // 1. Credit POSITIONS (decrease asset - remove at entry cost)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.MARGIN_CALL)
                .positionId(positionId)
                .account(AccountType.POSITIONS)
                .debit(BigDecimal.ZERO)
                .credit(sizeUsdt)
                .description("MARGIN CALL: Position liquidated - " + symbol)
                .metadata(metadataJson)
                .build());
        
        // 2. Debit REALIZED_PNL (record the loss)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.MARGIN_CALL)
                .positionId(positionId)
                .account(AccountType.REALIZED_PNL)
                .debit(realizedPnl.abs())
                .credit(BigDecimal.ZERO)
                .description("MARGIN CALL: Loss realized - " + symbol)
                .metadata(metadataJson)
                .build());
        
        // 3. Debit CASH (return any remaining value, if any)
        if (cashReturned.compareTo(BigDecimal.ZERO) > 0) {
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.MARGIN_CALL)
                    .positionId(positionId)
                    .account(AccountType.CASH)
                    .debit(cashReturned)
                    .credit(BigDecimal.ZERO)
                    .description("MARGIN CALL: Remaining capital returned - " + symbol)
                    .metadata(metadataJson)
                    .build());
        }
        
        // Calculate running balances
        calculateRunningBalances(entries);
        
        // Save all entries
        ledgerRepository.saveAll(entries);
        
        log.warn("Recorded MARGIN_CALL position {}: loss={}, cashReturned={}, txId={}", 
                positionId, realizedPnl, cashReturned, txId);
        
        return txId;
    }
    
    /**
     * Record a system reset with initial capital.
     */
    @Transactional
    public UUID recordReset(BigDecimal initialCapital) {
        // Clear all existing entries
        ledgerRepository.deleteAll();
        
        UUID txId = UUID.randomUUID();
        Instant now = Instant.now();
        
        Map<String, Object> metadata = Map.of(
            "initialCapital", initialCapital,
            "resetTimestamp", now.toString()
        );
        String metadataJson = toJson(metadata);
        
        List<LedgerEntry> entries = new ArrayList<>();
        
        // 1. Credit STARTING_CAPITAL (establish equity)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.RESET)
                .account(AccountType.STARTING_CAPITAL)
                .debit(BigDecimal.ZERO)
                .credit(initialCapital)
                .runningBalance(initialCapital)
                .description("System reset: Initial capital established")
                .metadata(metadataJson)
                .build());
        
        // 2. Debit CASH (establish asset)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.RESET)
                .account(AccountType.CASH)
                .debit(initialCapital)
                .credit(BigDecimal.ZERO)
                .runningBalance(initialCapital)
                .description("System reset: Cash balance established")
                .metadata(metadataJson)
                .build());
        
        // Save all entries
        ledgerRepository.saveAll(entries);
        
        log.info("Recorded RESET: initialCapital={}, txId={}", initialCapital, txId);
        
        return txId;
    }
    
    // ========== BALANCE CALCULATIONS ==========
    
    /**
     * Get current cash balance.
     * Cash = Starting Capital - (deployed to positions) + (returned from closes) - (trading costs)
     */
    public BigDecimal getCashBalance() {
        BigDecimal netBalance = ledgerRepository.calculateNetBalance(AccountType.CASH);
        return netBalance != null ? netBalance : BigDecimal.ZERO;
    }
    
    /**
     * Get total value of open positions (at entry cost).
     */
    public BigDecimal getPositionsValue() {
        BigDecimal netBalance = ledgerRepository.calculateNetBalance(AccountType.POSITIONS);
        return netBalance != null ? netBalance : BigDecimal.ZERO;
    }
    
    /**
     * Get total realized PnL.
     */
    public BigDecimal getRealizedPnl() {
        BigDecimal credits = ledgerRepository.sumCreditsByAccount(AccountType.REALIZED_PNL);
        BigDecimal debits = ledgerRepository.sumDebitsByAccount(AccountType.REALIZED_PNL);
        return (credits != null ? credits : BigDecimal.ZERO)
                .subtract(debits != null ? debits : BigDecimal.ZERO);
    }
    
    /**
     * Get total trading costs.
     */
    public BigDecimal getTradingCosts() {
        BigDecimal netBalance = ledgerRepository.calculateNetBalance(AccountType.TRADING_COSTS);
        return netBalance != null ? netBalance : BigDecimal.ZERO;
    }
    
    /**
     * Get starting capital.
     */
    public BigDecimal getStartingCapitalFromLedger() {
        BigDecimal credits = ledgerRepository.sumCreditsByAccount(AccountType.STARTING_CAPITAL);
        return credits != null ? credits : BigDecimal.ZERO;
    }
    
    /**
     * Calculate total equity from ledger.
     * Total Equity = Cash + Positions Value (at market) 
     * 
     * Note: This returns cash + positions at ENTRY cost.
     * For true equity including unrealized PnL, add the unrealized PnL separately.
     */
    public BigDecimal getBookEquity() {
        return getCashBalance().add(getPositionsValue());
    }
    
    // ========== RECONCILIATION ==========
    
    /**
     * Perform full reconciliation of the books.
     */
    public ReconciliationReport reconcile() {
        BigDecimal totalDebits = ledgerRepository.sumAllDebits();
        BigDecimal totalCredits = ledgerRepository.sumAllCredits();
        BigDecimal imbalance = (totalDebits != null ? totalDebits : BigDecimal.ZERO)
                .subtract(totalCredits != null ? totalCredits : BigDecimal.ZERO);
        
        // Get all account balances
        Map<String, BigDecimal> balances = new HashMap<>();
        for (AccountType account : AccountType.values()) {
            BigDecimal balance;
            if (account.isAsset() || account.isExpense()) {
                balance = ledgerRepository.calculateNetBalance(account);
            } else {
                // Equity accounts: credits - debits
                BigDecimal credits = ledgerRepository.sumCreditsByAccount(account);
                BigDecimal debits = ledgerRepository.sumDebitsByAccount(account);
                balance = (credits != null ? credits : BigDecimal.ZERO)
                        .subtract(debits != null ? debits : BigDecimal.ZERO);
            }
            balances.put(account.name(), balance != null ? balance : BigDecimal.ZERO);
        }
        
        // Calculate equity from components
        BigDecimal cash = balances.get(AccountType.CASH.name());
        BigDecimal positions = balances.get(AccountType.POSITIONS.name());
        BigDecimal startCap = balances.get(AccountType.STARTING_CAPITAL.name());
        BigDecimal realizedPnl = balances.get(AccountType.REALIZED_PNL.name());
        BigDecimal costs = balances.get(AccountType.TRADING_COSTS.name());
        
        BigDecimal calculatedEquity = cash.add(positions);
        BigDecimal expectedEquity = startCap.add(realizedPnl).subtract(costs);
        
        List<String> discrepancies = new ArrayList<>();
        
        // Check if balanced
        if (imbalance.abs().compareTo(new BigDecimal("0.00000001")) > 0) {
            discrepancies.add("Total debits (" + totalDebits + ") != credits (" + totalCredits + ")");
        }
        
        // Check accounting equation
        BigDecimal equityDiff = calculatedEquity.subtract(expectedEquity).abs();
        if (equityDiff.compareTo(new BigDecimal("0.01")) > 0) {
            discrepancies.add("Assets (" + calculatedEquity + ") != Equity (" + expectedEquity + ")");
        }
        
        return ReconciliationReport.builder()
                .balanced(discrepancies.isEmpty())
                .timestamp(Instant.now())
                .totalDebits(totalDebits != null ? totalDebits : BigDecimal.ZERO)
                .totalCredits(totalCredits != null ? totalCredits : BigDecimal.ZERO)
                .imbalance(imbalance)
                .accountBalances(balances)
                .calculatedEquity(calculatedEquity)
                .expectedEquity(expectedEquity)
                .discrepancies(discrepancies)
                .totalEntries(ledgerRepository.count())
                .totalTransactions(countDistinctTransactions())
                .build();
    }
    
    /**
     * Check if the ledger has been initialized with a reset.
     */
    public boolean isInitialized() {
        return ledgerRepository.count() > 0;
    }
    
    // ========== AUDIT ==========
    
    /**
     * Get ledger entries for a position.
     */
    public List<LedgerEntry> getPositionHistory(String positionId) {
        return ledgerRepository.findByPositionIdOrderByTimestampAsc(positionId);
    }
    
    /**
     * Get ledger entries for an account.
     */
    public List<LedgerEntry> getAccountHistory(AccountType account) {
        return ledgerRepository.findByAccountOrderByTimestampAsc(account);
    }
    
    /**
     * Get recent entries for an account.
     */
    public List<LedgerEntry> getRecentAccountHistory(AccountType account) {
        return ledgerRepository.findTop100ByAccountOrderByTimestampDesc(account);
    }
    
    /**
     * Get entries within a time range.
     */
    public List<LedgerEntry> getEntriesInRange(Instant from, Instant to) {
        return ledgerRepository.findByTimestampBetweenOrderByTimestampAsc(from, to);
    }
    
    // ========== HELPERS ==========
    
    private void calculateRunningBalances(List<LedgerEntry> entries) {
        for (LedgerEntry entry : entries) {
            BigDecimal currentBalance = ledgerRepository.calculateNetBalance(entry.getAccount());
            if (currentBalance == null) currentBalance = BigDecimal.ZERO;
            
            BigDecimal newBalance;
            if (entry.getAccount().isAsset() || entry.getAccount().isExpense()) {
                newBalance = currentBalance.add(entry.getDebit()).subtract(entry.getCredit());
            } else {
                newBalance = currentBalance.add(entry.getCredit()).subtract(entry.getDebit());
            }
            entry.setRunningBalance(newBalance.setScale(8, RoundingMode.HALF_UP));
        }
    }
    
    private long countDistinctTransactions() {
        // Approximate by counting reset + open + close entries
        return ledgerRepository.countByTransactionType(TransactionType.RESET) +
               ledgerRepository.countByTransactionType(TransactionType.OPEN) +
               ledgerRepository.countByTransactionType(TransactionType.CLOSE);
    }
    
    private String toJson(Map<String, Object> map) {
        try {
            return objectMapper.writeValueAsString(map);
        } catch (JsonProcessingException e) {
            return "{}";
        }
    }
}

