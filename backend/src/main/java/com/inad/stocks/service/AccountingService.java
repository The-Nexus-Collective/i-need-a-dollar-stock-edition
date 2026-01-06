package com.inad.stocks.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.inad.stocks.dto.ReconciliationReport;
import com.inad.stocks.entity.LedgerEntry;
import com.inad.stocks.entity.enums.AccountType;
import com.inad.stocks.entity.enums.TransactionType;
import com.inad.stocks.repository.LedgerRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import jakarta.annotation.PostConstruct;
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
    
    @Value("${trading.capital.starting:0}")
    private BigDecimal startingCapital;
    
    @PostConstruct
    public void init() {
        if (!isInitialized()) {
            log.info("Ledger not initialized - initializing with starting capital: {}", startingCapital);
            recordReset(startingCapital);
        } else {
            log.info("Ledger already initialized. Cash balance: {}", getCashBalance());
        }
    }
    
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
     * Record extending (adding to) an existing position.
     * 
     * Debits:
     *   - POSITIONS: addedSize (asset increase)
     *   - TRADING_COSTS: totalCosts (expense)
     * 
     * Credits:
     *   - CASH: addedSize + totalCosts (asset decrease)
     */
    @Transactional
    public UUID recordExtendPosition(String positionId, String symbol, BigDecimal addedSize,
                                     BigDecimal fee, BigDecimal spread, BigDecimal slippage,
                                     BigDecimal price, String direction) {
        UUID txId = UUID.randomUUID();
        Instant now = Instant.now();
        BigDecimal totalCosts = fee.add(spread).add(slippage);
        BigDecimal totalDeducted = addedSize.add(totalCosts);
        
        // Build metadata
        Map<String, Object> metadata = Map.of(
            "symbol", symbol,
            "direction", direction,
            "price", price,
            "addedSize", addedSize,
            "fee", fee,
            "spread", spread,
            "slippage", slippage,
            "operation", "EXTEND"
        );
        String metadataJson = toJson(metadata);
        
        List<LedgerEntry> entries = new ArrayList<>();
        
        // 1. Debit POSITIONS (increase asset)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.EXTEND)
                .positionId(positionId)
                .account(AccountType.POSITIONS)
                .debit(addedSize)
                .credit(BigDecimal.ZERO)
                .description("Position extended: " + direction + " " + symbol + " +" + addedSize + " USDT")
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
                    .description("Extension costs: fee=" + fee + ", spread=" + spread + ", slippage=" + slippage)
                    .metadata(metadataJson)
                    .build());
        }
        
        // 3. Credit CASH (decrease asset)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.EXTEND)
                .positionId(positionId)
                .account(AccountType.CASH)
                .debit(BigDecimal.ZERO)
                .credit(totalDeducted)
                .description("Capital deployed for extending " + symbol)
                .metadata(metadataJson)
                .build());
        
        // Calculate running balances
        calculateRunningBalances(entries);
        
        // Save all entries
        ledgerRepository.saveAll(entries);
        
        log.info("Recorded EXTEND position {}: addedSize={}, costs={}, txId={}", 
                positionId, addedSize, totalCosts, txId);
        
        return txId;
    }
    
    /**
     * Record reducing (partially closing) an existing position.
     * 
     * Credits:
     *   - POSITIONS: reducedSize (asset decrease - remove portion at entry cost)
     *   - REALIZED_PNL: partialPnl if profit (equity increase)
     * 
     * Debits:
     *   - CASH: reducedSize + partialPnl - exitCosts (asset increase - return capital)
     *   - REALIZED_PNL: |partialPnl| if loss (equity decrease)
     *   - TRADING_COSTS: exitCosts (expense)
     */
    @Transactional
    public UUID recordReducePosition(String positionId, String symbol, BigDecimal reducedSize,
                                     BigDecimal partialPnl, BigDecimal exitFee,
                                     BigDecimal exitPrice, int scalePercent) {
        UUID txId = UUID.randomUUID();
        Instant now = Instant.now();
        BigDecimal cashReturned = reducedSize.add(partialPnl).subtract(exitFee);
        
        // Build metadata
        Map<String, Object> metadata = Map.of(
            "symbol", symbol,
            "exitPrice", exitPrice,
            "reducedSize", reducedSize,
            "partialPnl", partialPnl,
            "exitFee", exitFee,
            "scalePercent", scalePercent,
            "operation", "REDUCE"
        );
        String metadataJson = toJson(metadata);
        
        List<LedgerEntry> entries = new ArrayList<>();
        
        // 1. Credit POSITIONS (decrease asset - remove at entry cost)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.REDUCE)
                .positionId(positionId)
                .account(AccountType.POSITIONS)
                .debit(BigDecimal.ZERO)
                .credit(reducedSize)
                .description("Position reduced: " + symbol + " -" + scalePercent + "%")
                .metadata(metadataJson)
                .build());
        
        // 2. Record PnL
        if (partialPnl.compareTo(BigDecimal.ZERO) >= 0) {
            // Profit: Credit REALIZED_PNL (increase equity)
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.REDUCE)
                    .positionId(positionId)
                    .account(AccountType.REALIZED_PNL)
                    .debit(BigDecimal.ZERO)
                    .credit(partialPnl)
                    .description("Partial profit realized: " + symbol)
                    .metadata(metadataJson)
                    .build());
        } else {
            // Loss: Debit REALIZED_PNL (decrease equity)
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.REDUCE)
                    .positionId(positionId)
                    .account(AccountType.REALIZED_PNL)
                    .debit(partialPnl.abs())
                    .credit(BigDecimal.ZERO)
                    .description("Partial loss realized: " + symbol)
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
                    .description("Reduction fee: " + symbol)
                    .metadata(metadataJson)
                    .build());
        }
        
        // 4. Debit CASH (increase asset - return capital with PnL)
        entries.add(LedgerEntry.builder()
                .transactionId(txId)
                .timestamp(now)
                .transactionType(TransactionType.REDUCE)
                .positionId(positionId)
                .account(AccountType.CASH)
                .debit(cashReturned)
                .credit(BigDecimal.ZERO)
                .description("Capital returned from reducing " + symbol)
                .metadata(metadataJson)
                .build());
        
        // Calculate running balances
        calculateRunningBalances(entries);
        
        // Save all entries
        ledgerRepository.saveAll(entries);
        
        log.info("Recorded REDUCE position {}: reducedSize={}, partialPnl={}, cashReturned={}, txId={}", 
                positionId, reducedSize, partialPnl, cashReturned, txId);
        
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
    
    // ========== FUNDING OPERATIONS ==========
    
    /**
     * Record a funding fee payment.
     * 
     * Positive fundingFee = payment (cost for longs when rate is positive)
     * Negative fundingFee = receipt (income for shorts when rate is positive)
     */
    @Transactional
    public UUID recordFundingPayment(String positionId, String symbol,
                                      BigDecimal fundingFee, BigDecimal fundingRate) {
        UUID txId = UUID.randomUUID();
        Instant now = Instant.now();
        
        Map<String, Object> metadata = Map.of(
            "symbol", symbol,
            "fundingRate", fundingRate,
            "fundingFee", fundingFee,
            "isPayment", fundingFee.compareTo(BigDecimal.ZERO) > 0
        );
        String metadataJson = toJson(metadata);
        
        List<LedgerEntry> entries = new ArrayList<>();
        
        if (fundingFee.compareTo(BigDecimal.ZERO) > 0) {
            // Payment (cost) - Debit TRADING_COSTS, Credit CASH
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.FUNDING)
                    .positionId(positionId)
                    .account(AccountType.TRADING_COSTS)
                    .debit(fundingFee)
                    .credit(BigDecimal.ZERO)
                    .description("Funding payment: " + symbol + " @ " + fundingRate)
                    .metadata(metadataJson)
                    .build());
            
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.FUNDING)
                    .positionId(positionId)
                    .account(AccountType.CASH)
                    .debit(BigDecimal.ZERO)
                    .credit(fundingFee)
                    .description("Funding payment: " + symbol)
                    .metadata(metadataJson)
                    .build());
        } else if (fundingFee.compareTo(BigDecimal.ZERO) < 0) {
            // Receipt (income) - Debit CASH, Credit REALIZED_PNL
            BigDecimal income = fundingFee.abs();
            
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.FUNDING)
                    .positionId(positionId)
                    .account(AccountType.CASH)
                    .debit(income)
                    .credit(BigDecimal.ZERO)
                    .description("Funding income: " + symbol + " @ " + fundingRate)
                    .metadata(metadataJson)
                    .build());
            
            entries.add(LedgerEntry.builder()
                    .transactionId(txId)
                    .timestamp(now)
                    .transactionType(TransactionType.FUNDING)
                    .positionId(positionId)
                    .account(AccountType.REALIZED_PNL)
                    .debit(BigDecimal.ZERO)
                    .credit(income)
                    .description("Funding income: " + symbol)
                    .metadata(metadataJson)
                    .build());
        }
        
        if (!entries.isEmpty()) {
            calculateRunningBalances(entries);
            ledgerRepository.saveAll(entries);
            
            log.debug("Recorded funding {}: {} @ rate {} = {} USDT, txId={}", 
                    symbol, fundingFee.compareTo(BigDecimal.ZERO) > 0 ? "payment" : "income",
                    fundingRate, fundingFee.abs(), txId);
        }
        
        return txId;
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
    
    /**
     * Get total spread costs from all TRADING_COSTS entries.
     * Spread is stored in metadata JSON of FEE transaction type entries.
     */
    public BigDecimal getTotalSpread() {
        return aggregateCostFromMetadata("spread");
    }
    
    /**
     * Get total slippage costs from all TRADING_COSTS entries.
     * Slippage is stored in metadata JSON of FEE transaction type entries.
     */
    public BigDecimal getTotalSlippage() {
        return aggregateCostFromMetadata("slippage");
    }
    
    /**
     * Get total fees (without spread/slippage) from metadata.
     */
    public BigDecimal getTotalFees() {
        return aggregateCostFromMetadata("fee");
    }
    
    /**
     * Aggregate a specific cost type from TRADING_COSTS entry metadata.
     */
    @SuppressWarnings("unchecked")
    private BigDecimal aggregateCostFromMetadata(String costField) {
        List<LedgerEntry> tradingCostEntries = ledgerRepository.findByAccountOrderByTimestampAsc(AccountType.TRADING_COSTS);
        BigDecimal total = BigDecimal.ZERO;
        
        for (LedgerEntry entry : tradingCostEntries) {
            if (entry.getMetadata() != null && !entry.getMetadata().isEmpty()) {
                try {
                    Map<String, Object> metadata = objectMapper.readValue(entry.getMetadata(), Map.class);
                    Object value = metadata.get(costField);
                    if (value != null) {
                        BigDecimal cost;
                        if (value instanceof Number) {
                            cost = new BigDecimal(value.toString());
                        } else if (value instanceof String) {
                            cost = new BigDecimal((String) value);
                        } else {
                            continue;
                        }
                        total = total.add(cost);
                    }
                } catch (Exception e) {
                    log.debug("Failed to parse metadata for cost aggregation: {}", e.getMessage());
                }
            }
        }
        
        return total.setScale(8, RoundingMode.HALF_UP);
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

