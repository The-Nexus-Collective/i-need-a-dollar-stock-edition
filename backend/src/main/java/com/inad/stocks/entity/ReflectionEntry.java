package com.inad.stocks.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Post-trade reflection entry for the learning timeline.
 * 
 * Records AI's self-reflection after a trade closes:
 * - Was the Pre-Mortem prediction correct?
 * - What lesson was learned (if any)?
 */
@Entity
@Table(name = "reflection_entries")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ReflectionEntry {

    @Id
    @Column(length = 36)
    private String id;

    @Column(name = "position_id", length = 32)
    private String positionId;

    @Column(length = 20)
    private String symbol;

    @Column(length = 10)
    private String direction;

    @Column(name = "entry_price", precision = 20, scale = 8)
    private BigDecimal entryPrice;

    @Column(name = "exit_price", precision = 20, scale = 8)
    private BigDecimal exitPrice;

    @Column(name = "pnl_percent", precision = 10, scale = 4)
    private BigDecimal pnlPercent;

    @Column(name = "hold_hours")
    private Integer holdHours;

    @Column(name = "pre_mortem", columnDefinition = "TEXT")
    private String preMortem;

    @Column(name = "what_happened", columnDefinition = "TEXT")
    private String whatHappened;

    @Column(name = "pre_mortem_was_correct")
    private Boolean preMortemWasCorrect;

    @Enumerated(EnumType.STRING)
    @Column(name = "lesson_type", length = 20)
    private TradeWisdom.WisdomType lessonType;

    @Column(name = "lesson_learned", columnDefinition = "TEXT")
    private String lessonLearned;

    @Column(name = "reflected_at", nullable = false)
    private Instant reflectedAt;
}

