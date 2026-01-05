package com.inad.stocks.controller;

import com.inad.stocks.dto.TransactionDTO;
import com.inad.stocks.entity.enums.TransactionType;
import com.inad.stocks.service.TransactionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * REST API for transaction history.
 * Provides the /api/transactions endpoint for the frontend History page.
 */
@Slf4j
@RestController
@RequestMapping("/api/transactions")
@RequiredArgsConstructor
public class TransactionController {
    
    private final TransactionService transactionService;
    
    /**
     * Get list of transactions for the History page.
     * 
     * @param limit Maximum number of transactions to return (default 100)
     * @param type Optional comma-separated transaction types to filter (OPEN,CLOSE,EXTEND,REDUCE)
     * @param includeLedger Whether to include full ledger entry details (default false)
     * @return List of transactions
     */
    @GetMapping
    public List<TransactionDTO> getTransactions(
            @RequestParam(defaultValue = "100") int limit,
            @RequestParam(required = false) String type,
            @RequestParam(name = "include_ledger", defaultValue = "false") boolean includeLedger) {
        
        log.info("Fetching transactions: limit={}, type={}, includeLedger={}", limit, type, includeLedger);
        
        List<TransactionType> types = null;
        if (type != null && !type.isEmpty()) {
            types = Arrays.stream(type.split(","))
                    .map(String::trim)
                    .map(String::toUpperCase)
                    .map(t -> {
                        try {
                            return TransactionType.valueOf(t);
                        } catch (IllegalArgumentException e) {
                            log.warn("Unknown transaction type: {}", t);
                            return null;
                        }
                    })
                    .filter(java.util.Objects::nonNull)
                    .collect(Collectors.toList());
        }
        
        return transactionService.getTransactions(limit, types, includeLedger);
    }
    
    /**
     * Get a single transaction with full ledger detail.
     * 
     * @param txId Transaction UUID
     * @return Transaction with ledger entries
     */
    @GetMapping("/{txId}")
    public ResponseEntity<TransactionDTO> getTransaction(@PathVariable UUID txId) {
        log.info("Fetching transaction: {}", txId);
        
        TransactionDTO transaction = transactionService.getTransaction(txId);
        if (transaction == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(transaction);
    }
    
    /**
     * Get transactions for a specific position.
     * Shows the full lifecycle of a position (OPEN → EXTEND → REDUCE → CLOSE).
     * 
     * @param positionId Position ID
     * @param includeLedger Whether to include full ledger entry details
     * @return List of transactions for the position
     */
    @GetMapping("/position/{positionId}")
    public List<TransactionDTO> getPositionTransactions(
            @PathVariable String positionId,
            @RequestParam(name = "include_ledger", defaultValue = "false") boolean includeLedger) {
        
        log.info("Fetching transactions for position: {}", positionId);
        return transactionService.getTransactionsForPosition(positionId, includeLedger);
    }
    
    /**
     * Get transaction summary statistics.
     * 
     * @return Summary with counts by type and totals
     */
    @GetMapping("/summary")
    public Map<String, Object> getTransactionSummary() {
        log.info("Fetching transaction summary");
        return transactionService.getTransactionSummary();
    }
    
    /**
     * Export transactions to CSV format.
     * 
     * @param limit Maximum number of transactions to export
     * @param type Optional comma-separated transaction types to filter
     * @return CSV file download
     */
    @GetMapping("/export")
    public ResponseEntity<String> exportTransactions(
            @RequestParam(defaultValue = "0") int limit,
            @RequestParam(required = false) String type,
            @RequestParam(defaultValue = "csv") String format) {
        
        log.info("Exporting transactions: limit={}, type={}, format={}", limit, type, format);
        
        List<TransactionType> types = null;
        if (type != null && !type.isEmpty()) {
            types = Arrays.stream(type.split(","))
                    .map(String::trim)
                    .map(String::toUpperCase)
                    .map(t -> {
                        try {
                            return TransactionType.valueOf(t);
                        } catch (IllegalArgumentException e) {
                            return null;
                        }
                    })
                    .filter(java.util.Objects::nonNull)
                    .collect(Collectors.toList());
        }
        
        List<TransactionDTO> transactions = transactionService.getTransactions(limit, types, false);
        
        if ("csv".equalsIgnoreCase(format)) {
            String csv = transactionService.exportToCsv(transactions);
            
            String filename = "transactions_" + 
                    DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")
                            .withZone(ZoneId.of("UTC"))
                            .format(Instant.now()) + ".csv";
            
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                    .contentType(MediaType.parseMediaType("text/csv"))
                    .body(csv);
        }
        
        // For future: add PDF support
        return ResponseEntity.badRequest().body("Unsupported format: " + format);
    }
}

