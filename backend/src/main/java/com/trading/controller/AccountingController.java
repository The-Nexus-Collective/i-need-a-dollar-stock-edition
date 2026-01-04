package com.trading.controller;

import com.trading.dto.ReconciliationReport;
import com.trading.entity.LedgerEntry;
import com.trading.entity.enums.AccountType;
import com.trading.service.AccountingService;
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

