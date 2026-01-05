package com.trading.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

import java.time.Instant;

/**
 * Accumulated wisdom from past trades.
 * 
 * Types:
 * - WARNING_SIGNAL: Pre-Mortems that came true (Grok was right to worry)
 * - BLIND_SPOT: Risks that Grok didn't anticipate
 * - TIME_LESSON: Learnings about trade duration expectations
 */
@Entity
@Table(name = "trade_wisdom")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TradeWisdom {

    @Id
    @Column(length = 36)
    private String id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private WisdomType type;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String description;

    @Column(nullable = false)
    @Builder.Default
    private int occurrences = 1;

    @Column(name = "first_occurred", nullable = false)
    private Instant firstOccurred;

    @Column(name = "last_occurred", nullable = false)
    private Instant lastOccurred;

    @Column(name = "symbol_pattern", length = 20)
    private String symbolPattern;

    @Column(name = "direction_pattern", length = 10)
    private String directionPattern;

    public enum WisdomType {
        WARNING_SIGNAL,  // Pre-Mortem that came true
        BLIND_SPOT,      // Risk that wasn't anticipated
        TIME_LESSON      // Learning about trade duration
    }

    /**
     * Increment occurrence count and update last occurred timestamp.
     */
    public void incrementOccurrence() {
        this.occurrences++;
        this.lastOccurred = Instant.now();
    }
}

