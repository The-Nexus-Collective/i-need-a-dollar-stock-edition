package com.inad.stocks.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.inad.stocks.dto.LedgerEntryDTO;
import com.inad.stocks.dto.TransactionDTO;
import com.inad.stocks.entity.LedgerEntry;
import com.inad.stocks.entity.Position;
import com.inad.stocks.entity.enums.AccountType;
import com.inad.stocks.entity.enums.TransactionType;
import com.inad.stocks.repository.LedgerRepository;
import com.inad.stocks.repository.PositionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.StringWriter;
import java.io.PrintWriter;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Service for aggregating ledger entries into user-friendly transactions.
 * Bridges the double-entry accounting system with the frontend History page.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TransactionService {
    
    private final LedgerRepository ledgerRepository;
    private final PositionRepository positionRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    // Transaction types to show in history (excludes FEE entries which are part of OPEN/CLOSE)
    private static final List<TransactionType> DISPLAYABLE_TYPES = List.of(
            TransactionType.OPEN,
            TransactionType.CLOSE,
            TransactionType.EXTEND,
            TransactionType.REDUCE,
            TransactionType.RESET,
            TransactionType.MARGIN_CALL
    );
    
    /**
     * Get all transactions for the History page.
     * 
     * @param limit Maximum number of transactions to return
     * @param types Optional filter by transaction types
     * @param includeLedgerEntries Whether to include full ledger entry details
     * @return List of transactions ordered by timestamp descending
     */
    public List<TransactionDTO> getTransactions(int limit, List<TransactionType> types, boolean includeLedgerEntries) {
        // Determine which types to query
        List<TransactionType> queryTypes = (types != null && !types.isEmpty()) 
                ? types 
                : DISPLAYABLE_TYPES;
        
        // Get all ledger entries for the requested types
        List<LedgerEntry> allEntries = ledgerRepository.findByTransactionTypesOrderByTimestampDesc(queryTypes);
        
        // Group entries by transaction_id
        Map<UUID, List<LedgerEntry>> entriesByTxId = allEntries.stream()
                .collect(Collectors.groupingBy(LedgerEntry::getTransactionId));
        
        // Build transactions from grouped entries
        List<TransactionDTO> transactions = new ArrayList<>();
        
        for (Map.Entry<UUID, List<LedgerEntry>> entry : entriesByTxId.entrySet()) {
            UUID txId = entry.getKey();
            List<LedgerEntry> txEntries = entry.getValue();
            
            TransactionDTO transaction = buildTransaction(txId, txEntries, includeLedgerEntries);
            if (transaction != null) {
                transactions.add(transaction);
            }
        }
        
        // Sort by timestamp descending and apply limit
        transactions.sort((a, b) -> b.getTimestamp().compareTo(a.getTimestamp()));
        
        if (limit > 0 && transactions.size() > limit) {
            return transactions.subList(0, limit);
        }
        
        return transactions;
    }
    
    /**
     * Get a single transaction with full ledger detail.
     */
    public TransactionDTO getTransaction(UUID transactionId) {
        List<LedgerEntry> entries = ledgerRepository.findByTransactionId(transactionId);
        if (entries.isEmpty()) {
            return null;
        }
        return buildTransaction(transactionId, entries, true);
    }
    
    /**
     * Get transactions for a specific position.
     */
    public List<TransactionDTO> getTransactionsForPosition(String positionId, boolean includeLedgerEntries) {
        List<LedgerEntry> entries = ledgerRepository.findByPositionIdOrderByTimestampAsc(positionId);
        
        // Group by transaction_id
        Map<UUID, List<LedgerEntry>> entriesByTxId = entries.stream()
                .collect(Collectors.groupingBy(LedgerEntry::getTransactionId));
        
        List<TransactionDTO> transactions = new ArrayList<>();
        for (Map.Entry<UUID, List<LedgerEntry>> entry : entriesByTxId.entrySet()) {
            TransactionDTO transaction = buildTransaction(entry.getKey(), entry.getValue(), includeLedgerEntries);
            if (transaction != null) {
                transactions.add(transaction);
            }
        }
        
        transactions.sort(Comparator.comparing(TransactionDTO::getTimestamp));
        return transactions;
    }
    
    /**
     * Export transactions to CSV format.
     */
    public String exportToCsv(List<TransactionDTO> transactions) {
        StringWriter sw = new StringWriter();
        PrintWriter pw = new PrintWriter(sw);
        
        // Header
        pw.println("Timestamp,Type,Symbol,Direction,Size (USDT),Price,Leverage,Fee,Spread,Slippage,Total Costs,Gross PnL,Net PnL,PnL %,Conviction,Reason");
        
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
                .withZone(ZoneId.of("UTC"));
        
        for (TransactionDTO tx : transactions) {
            pw.printf("%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,\"%s\"%n",
                    formatter.format(tx.getTimestamp()),
                    tx.getTransactionType(),
                    tx.getSymbol() != null ? tx.getSymbol() : "",
                    tx.getDirection() != null ? tx.getDirection() : "",
                    formatBigDecimal(tx.getSizeUsd()),
                    formatBigDecimal(tx.getPrice()),
                    tx.getLeverage() != null ? tx.getLeverage() : "",
                    formatBigDecimal(tx.getFee()),
                    formatBigDecimal(tx.getSpread()),
                    formatBigDecimal(tx.getSlippage()),
                    formatBigDecimal(tx.getTotalCosts()),
                    formatBigDecimal(tx.getGrossPnl()),
                    formatBigDecimal(tx.getNetPnl()),
                    formatBigDecimal(tx.getPnlPercent()),
                    tx.getConviction() != null ? tx.getConviction() : "",
                    tx.getReason() != null ? tx.getReason().replace("\"", "'") : ""
            );
        }
        
        return sw.toString();
    }
    
    /**
     * Get transaction summary statistics.
     */
    public Map<String, Object> getTransactionSummary() {
        List<TransactionDTO> allTransactions = getTransactions(0, null, false);
        
        long openCount = allTransactions.stream()
                .filter(t -> t.getTransactionType() == TransactionType.OPEN).count();
        long closeCount = allTransactions.stream()
                .filter(t -> t.getTransactionType() == TransactionType.CLOSE).count();
        long extendCount = allTransactions.stream()
                .filter(t -> t.getTransactionType() == TransactionType.EXTEND).count();
        long reduceCount = allTransactions.stream()
                .filter(t -> t.getTransactionType() == TransactionType.REDUCE).count();
        
        BigDecimal totalFees = allTransactions.stream()
                .map(t -> t.getFee() != null ? t.getFee() : BigDecimal.ZERO)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        
        BigDecimal totalPnl = allTransactions.stream()
                .map(t -> t.getNetPnl() != null ? t.getNetPnl() : BigDecimal.ZERO)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        
        return Map.of(
                "totalTransactions", allTransactions.size(),
                "openCount", openCount,
                "closeCount", closeCount,
                "extendCount", extendCount,
                "reduceCount", reduceCount,
                "totalFees", totalFees,
                "totalPnl", totalPnl
        );
    }
    
    // ========== PRIVATE HELPERS ==========
    
    /**
     * Build a TransactionDTO from ledger entries.
     */
    private TransactionDTO buildTransaction(UUID txId, List<LedgerEntry> entries, boolean includeLedgerEntries) {
        if (entries.isEmpty()) {
            return null;
        }
        
        // Find the main entry (not FEE type)
        LedgerEntry mainEntry = entries.stream()
                .filter(e -> e.getTransactionType() != TransactionType.FEE)
                .findFirst()
                .orElse(entries.get(0));
        
        TransactionType type = mainEntry.getTransactionType();
        String positionId = mainEntry.getPositionId();
        
        // Parse metadata for additional details
        Map<String, Object> metadata = parseMetadata(mainEntry.getMetadata());
        
        // Get position details if available
        Position position = null;
        if (positionId != null) {
            position = positionRepository.findById(positionId).orElse(null);
        }
        
        // Calculate costs from entries
        BigDecimal fee = BigDecimal.ZERO;
        BigDecimal spread = BigDecimal.ZERO;
        BigDecimal slippage = BigDecimal.ZERO;
        BigDecimal grossPnl = BigDecimal.ZERO;
        BigDecimal sizeUsdt = BigDecimal.ZERO;
        
        for (LedgerEntry entry : entries) {
            if (entry.getAccount() == AccountType.TRADING_COSTS) {
                // Parse individual costs from metadata
                Map<String, Object> entryMeta = parseMetadata(entry.getMetadata());
                fee = fee.add(getBigDecimalFromMetadata(entryMeta, "fee"));
                spread = spread.add(getBigDecimalFromMetadata(entryMeta, "spread"));
                slippage = slippage.add(getBigDecimalFromMetadata(entryMeta, "slippage"));
                
                // If individual costs not available, use total
                if (fee.compareTo(BigDecimal.ZERO) == 0 && entry.getDebit() != null) {
                    fee = entry.getDebit();
                }
            } else if (entry.getAccount() == AccountType.REALIZED_PNL) {
                if (entry.isCredit()) {
                    grossPnl = grossPnl.add(entry.getCredit());
                } else {
                    grossPnl = grossPnl.subtract(entry.getDebit());
                }
            } else if (entry.getAccount() == AccountType.POSITIONS) {
                if (entry.isDebit()) {
                    sizeUsdt = sizeUsdt.add(entry.getDebit());
                } else {
                    sizeUsdt = sizeUsdt.add(entry.getCredit());
                }
            }
        }
        
        // Override with metadata values if available
        if (metadata.containsKey("sizeUsdt")) {
            sizeUsdt = getBigDecimalFromMetadata(metadata, "sizeUsdt");
        }
        if (metadata.containsKey("fee")) {
            fee = getBigDecimalFromMetadata(metadata, "fee");
        }
        if (metadata.containsKey("spread")) {
            spread = getBigDecimalFromMetadata(metadata, "spread");
        }
        if (metadata.containsKey("slippage")) {
            slippage = getBigDecimalFromMetadata(metadata, "slippage");
        }
        
        BigDecimal totalCosts = fee.add(spread).add(slippage);
        BigDecimal netPnl = grossPnl.subtract(totalCosts);
        
        // Calculate PnL percentage
        BigDecimal pnlPercent = BigDecimal.ZERO;
        if (sizeUsdt.compareTo(BigDecimal.ZERO) > 0 && netPnl.compareTo(BigDecimal.ZERO) != 0) {
            pnlPercent = netPnl.divide(sizeUsdt, 4, RoundingMode.HALF_UP)
                    .multiply(BigDecimal.valueOf(100));
        }
        
        // Build the DTO
        TransactionDTO.TransactionDTOBuilder builder = TransactionDTO.builder()
                .transactionId(txId)
                .timestamp(mainEntry.getTimestamp())
                .transactionType(type)
                .transactionTypeDisplay(formatTransactionType(type))
                .positionId(positionId)
                .sizeUsd(sizeUsdt)
                .fee(fee)
                .spread(spread)
                .slippage(slippage)
                .totalCosts(totalCosts)
                .grossPnl(grossPnl)
                .netPnl(netPnl)
                .pnlPercent(pnlPercent)
                .ledgerEntryCount(entries.size());
        
        // Add position-related fields
        if (position != null) {
            builder.symbol(position.getSymbol())
                    .direction(position.getDirection())
                    .price(position.getEntryPrice())
                    .quantity(position.getQuantity())
                    .leverage(position.getLeverage())
                    .conviction(position.getConviction() != null 
                            ? position.getConviction().intValue() : null)
                    .reason(position.getReasoning());
        } else {
            // Try to get from metadata
            builder.symbol(getStringFromMetadata(metadata, "symbol"))
                    .direction(getStringFromMetadata(metadata, "direction"))
                    .price(getBigDecimalFromMetadata(metadata, "entryPrice"))
                    .reason(getStringFromMetadata(metadata, "closeReason"));
        }
        
        // Add ledger entries if requested
        if (includeLedgerEntries) {
            List<LedgerEntryDTO> ledgerEntryDTOs = entries.stream()
                    .map(LedgerEntryDTO::fromEntity)
                    .collect(Collectors.toList());
            builder.ledgerEntries(ledgerEntryDTOs);
        }
        
        return builder.build();
    }
    
    private Map<String, Object> parseMetadata(String metadataJson) {
        if (metadataJson == null || metadataJson.isEmpty()) {
            return Collections.emptyMap();
        }
        try {
            return objectMapper.readValue(metadataJson, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            log.warn("Failed to parse metadata JSON: {}", e.getMessage());
            return Collections.emptyMap();
        }
    }
    
    private BigDecimal getBigDecimalFromMetadata(Map<String, Object> metadata, String key) {
        Object value = metadata.get(key);
        if (value == null) {
            return BigDecimal.ZERO;
        }
        if (value instanceof Number) {
            return BigDecimal.valueOf(((Number) value).doubleValue());
        }
        try {
            return new BigDecimal(value.toString());
        } catch (NumberFormatException e) {
            return BigDecimal.ZERO;
        }
    }
    
    private String getStringFromMetadata(Map<String, Object> metadata, String key) {
        Object value = metadata.get(key);
        return value != null ? value.toString() : null;
    }
    
    private String formatTransactionType(TransactionType type) {
        return switch (type) {
            case OPEN -> "Position Opened";
            case CLOSE -> "Position Closed";
            case EXTEND -> "Position Extended";
            case REDUCE -> "Position Reduced";
            case RESET -> "System Reset";
            case MARGIN_CALL -> "Margin Call - Liquidated";
            default -> type.name();
        };
    }
    
    private String formatBigDecimal(BigDecimal value) {
        if (value == null) {
            return "";
        }
        return value.setScale(2, RoundingMode.HALF_UP).toPlainString();
    }
}

