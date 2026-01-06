package com.inad.stocks.dto;

import com.inad.stocks.entity.LedgerEntry;
import com.inad.stocks.entity.enums.AccountType;
import com.inad.stocks.entity.enums.TransactionType;
import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * DTO for ledger entry display in the History page.
 * Simplified view of double-entry accounting entries.
 */
@Data
@Builder
public class LedgerEntryDTO {
    
    private Long id;
    private UUID transactionId;
    private Instant timestamp;
    private TransactionType transactionType;
    private String positionId;
    private AccountType account;
    private BigDecimal debit;
    private BigDecimal credit;
    private BigDecimal runningBalance;
    private String description;
    
    /**
     * Whether this is a debit entry (increases assets/expenses).
     */
    private boolean isDebit;
    
    /**
     * Human-readable account name.
     */
    private String accountDisplay;
    
    /**
     * Net effect on the account (positive = increase, negative = decrease).
     */
    private BigDecimal netEffect;
    
    /**
     * Convert from entity to DTO.
     */
    public static LedgerEntryDTO fromEntity(LedgerEntry entry) {
        return LedgerEntryDTO.builder()
                .id(entry.getId())
                .transactionId(entry.getTransactionId())
                .timestamp(entry.getTimestamp())
                .transactionType(entry.getTransactionType())
                .positionId(entry.getPositionId())
                .account(entry.getAccount())
                .debit(entry.getDebit())
                .credit(entry.getCredit())
                .runningBalance(entry.getRunningBalance())
                .description(entry.getDescription())
                .isDebit(entry.isDebit())
                .accountDisplay(formatAccountName(entry.getAccount()))
                .netEffect(entry.getNetEffect())
                .build();
    }
    
    private static String formatAccountName(AccountType account) {
        return switch (account) {
            case CASH -> "Cash";
            case POSITIONS -> "Positions";
            case REALIZED_PNL -> "Realized P&L";
            case TRADING_COSTS -> "Trading Costs";
            case STARTING_CAPITAL -> "Starting Capital";
        };
    }
}

