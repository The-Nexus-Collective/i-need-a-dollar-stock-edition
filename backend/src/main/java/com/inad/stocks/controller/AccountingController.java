package com.inad.stocks.controller;

import com.inad.stocks.dto.ReconciliationReport;
import com.inad.stocks.entity.LedgerEntry;
import com.inad.stocks.entity.enums.AccountType;
import com.inad.stocks.service.AccountingService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * REST API for accounting audit and reconciliation.
 */
@Slf4j
@RestController
@RequestMapping("/api/accounting")
@RequiredArgsConstructor
public class AccountingController {

    private final AccountingService accountingService;

    /**
     * Get all account balances.
     */
    @GetMapping("/balances")
    public Map<String, Object> getAccountBalances() {
        Map<String, Object> response = new HashMap<>();
        
        response.put("cash", accountingService.getCashBalance());
        response.put("positions", accountingService.getPositionsValue());
        response.put("realizedPnl", accountingService.getRealizedPnl());
        response.put("tradingCosts", accountingService.getTradingCosts());
        response.put("startingCapital", accountingService.getStartingCapitalFromLedger());
        response.put("bookEquity", accountingService.getBookEquity());
        response.put("initialized", accountingService.isInitialized());
        
        return response;
    }

    /**
     * Perform reconciliation and return report.
     */
    @GetMapping("/reconcile")
    public ReconciliationReport reconcile() {
        log.info("Performing accounting reconciliation");
        ReconciliationReport report = accountingService.reconcile();
        
        if (!report.isBalanced()) {
            log.warn("Reconciliation found discrepancies: {}", report.getDiscrepancies());
        } else {
            log.info("Reconciliation successful - books are balanced");
        }
        
        return report;
    }

    /**
     * Get ledger entries for a specific position.
     */
    @GetMapping("/ledger/position/{positionId}")
    public List<LedgerEntry> getPositionLedger(@PathVariable String positionId) {
        return accountingService.getPositionHistory(positionId);
    }

    /**
     * Get ledger entries for a specific account.
     */
    @GetMapping("/ledger/account/{account}")
    public List<LedgerEntry> getAccountLedger(@PathVariable String account) {
        try {
            AccountType accountType = AccountType.valueOf(account.toUpperCase());
            return accountingService.getAccountHistory(accountType);
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid account type: " + account + 
                    ". Valid types: CASH, POSITIONS, REALIZED_PNL, TRADING_COSTS, STARTING_CAPITAL");
        }
    }

    /**
     * Get recent ledger entries for an account.
     */
    @GetMapping("/ledger/account/{account}/recent")
    public List<LedgerEntry> getRecentAccountLedger(@PathVariable String account) {
        try {
            AccountType accountType = AccountType.valueOf(account.toUpperCase());
            return accountingService.getRecentAccountHistory(accountType);
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid account type: " + account);
        }
    }

    /**
     * Get ledger entries within a time range.
     */
    @GetMapping("/ledger")
    public List<LedgerEntry> getLedgerInRange(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime from,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime to) {
        Instant fromInstant = from.toInstant(ZoneOffset.UTC);
        Instant toInstant = to.toInstant(ZoneOffset.UTC);
        return accountingService.getEntriesInRange(fromInstant, toInstant);
    }

    /**
     * Get full accounting breakdown for debugging and visibility.
     * Returns all account balances, cost breakdown, and reconciliation status.
     */
    @GetMapping("/breakdown")
    public Map<String, Object> getAccountingBreakdown() {
        Map<String, Object> breakdown = new HashMap<>();
        
        // Core balances
        BigDecimal startingCapital = accountingService.getStartingCapitalFromLedger();
        BigDecimal cash = accountingService.getCashBalance();
        BigDecimal positionsValue = accountingService.getPositionsValue();
        BigDecimal realizedPnl = accountingService.getRealizedPnl();
        BigDecimal tradingCosts = accountingService.getTradingCosts();
        
        // Cost breakdown from metadata
        BigDecimal totalFees = accountingService.getTotalFees();
        BigDecimal totalSpread = accountingService.getTotalSpread();
        BigDecimal totalSlippage = accountingService.getTotalSlippage();
        
        // Equity calculations
        BigDecimal bookEquity = accountingService.getBookEquity(); // Cash + Positions (at cost)
        BigDecimal expectedEquity = startingCapital.add(realizedPnl).subtract(tradingCosts);
        
        // Reconciliation
        ReconciliationReport reconciliation = accountingService.reconcile();
        
        // Build response
        breakdown.put("startingCapital", startingCapital);
        breakdown.put("cashBalance", cash);
        breakdown.put("positionsValue", positionsValue);
        breakdown.put("realizedPnl", realizedPnl);
        
        // Cost breakdown
        Map<String, BigDecimal> costBreakdown = new HashMap<>();
        costBreakdown.put("totalTradingCosts", tradingCosts);
        costBreakdown.put("fees", totalFees);
        costBreakdown.put("spread", totalSpread);
        costBreakdown.put("slippage", totalSlippage);
        breakdown.put("costBreakdown", costBreakdown);
        
        // Equity analysis
        breakdown.put("bookEquity", bookEquity);
        breakdown.put("expectedEquity", expectedEquity);
        breakdown.put("equityDiscrepancy", bookEquity.subtract(expectedEquity));
        
        // Account balances from reconciliation
        breakdown.put("accountBalances", reconciliation.getAccountBalances());
        
        // Reconciliation status
        Map<String, Object> reconciliationStatus = new HashMap<>();
        reconciliationStatus.put("balanced", reconciliation.isBalanced());
        reconciliationStatus.put("totalDebits", reconciliation.getTotalDebits());
        reconciliationStatus.put("totalCredits", reconciliation.getTotalCredits());
        reconciliationStatus.put("imbalance", reconciliation.getImbalance());
        reconciliationStatus.put("discrepancies", reconciliation.getDiscrepancies());
        breakdown.put("reconciliation", reconciliationStatus);
        
        // Metadata
        breakdown.put("totalLedgerEntries", reconciliation.getTotalEntries());
        breakdown.put("totalTransactions", reconciliation.getTotalTransactions());
        breakdown.put("initialized", accountingService.isInitialized());
        breakdown.put("timestamp", java.time.Instant.now().toString());
        
        log.info("Accounting breakdown requested - bookEquity={}, expectedEquity={}, balanced={}", 
                bookEquity, expectedEquity, reconciliation.isBalanced());
        
        return breakdown;
    }

    /**
     * Health check - verify accounting system is working.
     */
    @GetMapping("/health")
    public Map<String, Object> healthCheck() {
        Map<String, Object> health = new HashMap<>();
        
        boolean initialized = accountingService.isInitialized();
        ReconciliationReport report = accountingService.reconcile();
        
        health.put("status", initialized && report.isBalanced() ? "HEALTHY" : "UNHEALTHY");
        health.put("initialized", initialized);
        health.put("balanced", report.isBalanced());
        health.put("totalEntries", report.getTotalEntries());
        health.put("cash", accountingService.getCashBalance());
        health.put("positions", accountingService.getPositionsValue());
        
        if (!report.getDiscrepancies().isEmpty()) {
            health.put("discrepancies", report.getDiscrepancies());
        }
        
        return health;
    }
}

