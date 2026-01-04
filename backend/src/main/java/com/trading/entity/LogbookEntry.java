package com.trading.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Trading cycle logbook entry.
 * Stores Grok's analysis text and all cycle details for display in the frontend.
 */
@Entity
@Table(name = "logbook_entry")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class LogbookEntry {
    
    @Id
    private String id;
    
    @Column(nullable = false)
    private Instant timestamp;
    
    @Column(name = "cycle_number", nullable = false)
    private int cycleNumber;
    
    // Grok analysis content
    @Column(name = "analysis_text", columnDefinition = "TEXT")
    private String analysisText;
    
    @Column(name = "market_summary", columnDefinition = "TEXT")
    private String marketSummary;
    
    // Actions taken (JSON arrays stored as text)
    @Column(name = "positions_closed", columnDefinition = "TEXT")
    private String positionsClosed;
    
    @Column(name = "positions_opened", columnDefinition = "TEXT")
    private String positionsOpened;
    
    @Column(name = "positions_kept", columnDefinition = "TEXT")
    private String positionsKept;
    
    @Column(name = "positions_extended", columnDefinition = "TEXT")
    private String positionsExtended;
    
    @Column(name = "positions_reduced", columnDefinition = "TEXT")
    private String positionsReduced;
    
    // Metrics
    @Column(name = "coins_analyzed")
    @Builder.Default
    private int coinsAnalyzed = 0;
    
    @Column(name = "coins_skipped")
    @Builder.Default
    private int coinsSkipped = 0;
    
    @Column(name = "tokens_used")
    @Builder.Default
    private int tokensUsed = 0;
    
    // Portfolio state at this point
    @Column(name = "total_equity", precision = 20, scale = 8)
    private BigDecimal totalEquity;
    
    @Column(name = "unrealized_pnl", precision = 20, scale = 8)
    private BigDecimal unrealizedPnl;
    
    @Column(name = "open_positions")
    @Builder.Default
    private int openPositions = 0;
    
    @Column(name = "deployment_percent", precision = 10, scale = 4)
    private BigDecimal deploymentPercent;
    
    // Debug: raw Grok I/O
    @Column(name = "raw_prompt", columnDefinition = "TEXT")
    private String rawPrompt;
    
    @Column(name = "raw_response", columnDefinition = "TEXT")
    private String rawResponse;
}

