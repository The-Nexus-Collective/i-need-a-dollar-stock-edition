package com.inad.stocks.controller;

import com.inad.stocks.dto.PositionPreMortemDTO;
import com.inad.stocks.entity.Position;
import com.inad.stocks.entity.ReflectionEntry;
import com.inad.stocks.entity.TradeWisdom;
import com.inad.stocks.entity.TradeWisdom.WisdomType;
import com.inad.stocks.repository.PositionRepository;
import com.inad.stocks.repository.ReflectionEntryRepository;
import com.inad.stocks.repository.TradeWisdomRepository;
import com.inad.stocks.service.LearningStatsService;
import com.inad.stocks.service.LearningStatsService.LearningStats;
import com.inad.stocks.service.PreMortemCheckerService;
import com.inad.stocks.service.PreMortemCheckerService.PreMortemCheckResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * REST Controller for the Self-Learning System.
 * 
 * Provides endpoints for:
 * - Accumulated wisdom (learnings)
 * - Learning timeline (reflections)
 * - Effectiveness statistics
 * - Pre-Mortem status for open positions
 */
@Slf4j
@RestController
@RequestMapping("/api/learning")
@RequiredArgsConstructor
public class LearningController {

    private final TradeWisdomRepository wisdomRepository;
    private final ReflectionEntryRepository reflectionRepository;
    private final LearningStatsService statsService;
    private final PreMortemCheckerService preMortemChecker;
    private final PositionRepository positionRepository;

    // ═══════════════════════════════════════════════════════════════════════════
    // WISDOM ENDPOINTS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Get all accumulated wisdom, ordered by occurrence count.
     */
    @GetMapping("/wisdom")
    public ResponseEntity<List<TradeWisdom>> getAllWisdom() {
        List<TradeWisdom> wisdoms = wisdomRepository.findAllByOrderByOccurrencesDesc();
        return ResponseEntity.ok(wisdoms);
    }

    /**
     * Get wisdom filtered by type.
     */
    @GetMapping("/wisdom/{type}")
    public ResponseEntity<List<TradeWisdom>> getWisdomByType(@PathVariable String type) {
        try {
            WisdomType wisdomType = WisdomType.valueOf(type.toUpperCase());
            List<TradeWisdom> wisdoms = wisdomRepository.findByTypeOrderByOccurrencesDesc(wisdomType);
            return ResponseEntity.ok(wisdoms);
        } catch (IllegalArgumentException e) {
            log.warn("Invalid wisdom type requested: {}", type);
            return ResponseEntity.badRequest().build();
        }
    }

    /**
     * Get wisdom summary by type counts.
     */
    @GetMapping("/wisdom/summary")
    public ResponseEntity<WisdomSummary> getWisdomSummary() {
        WisdomSummary summary = WisdomSummary.builder()
                .totalWisdoms((int) wisdomRepository.count())
                .warningSignals((int) wisdomRepository.countByType(WisdomType.WARNING_SIGNAL))
                .blindSpots((int) wisdomRepository.countByType(WisdomType.BLIND_SPOT))
                .timeLessons((int) wisdomRepository.countByType(WisdomType.TIME_LESSON))
                .build();
        return ResponseEntity.ok(summary);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // TIMELINE ENDPOINTS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Get learning timeline (recent reflections).
     */
    @GetMapping("/timeline")
    public ResponseEntity<List<ReflectionEntry>> getTimeline(
            @RequestParam(defaultValue = "20") int limit) {
        List<ReflectionEntry> timeline = reflectionRepository.findTopByOrderByReflectedAtDesc(
                PageRequest.of(0, limit));
        return ResponseEntity.ok(timeline);
    }

    /**
     * Get reflection for a specific position.
     */
    @GetMapping("/timeline/position/{positionId}")
    public ResponseEntity<List<ReflectionEntry>> getPositionReflections(
            @PathVariable String positionId) {
        List<ReflectionEntry> reflections = reflectionRepository.findByPositionIdOrderByReflectedAtDesc(positionId);
        return ResponseEntity.ok(reflections);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // STATS ENDPOINTS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Get comprehensive learning effectiveness statistics.
     */
    @GetMapping("/stats")
    public ResponseEntity<LearningStats> getStats() {
        LearningStats stats = statsService.calculateStats();
        return ResponseEntity.ok(stats);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PRE-MORTEM STATUS ENDPOINTS
    // ═══════════════════════════════════════════════════════════════════════════

    /**
     * Get Pre-Mortem status for all open positions.
     */
    @GetMapping("/positions/premortem-status")
    public ResponseEntity<List<PositionPreMortemDTO>> getOpenPositionsWithPreMortemStatus() {
        List<Position> openPositions = positionRepository.findOpenPositions();
        
        List<PositionPreMortemDTO> results = openPositions.stream()
                .map(pos -> {
                    PreMortemCheckResult check = preMortemChecker.checkPreMortem(pos);
                    return PositionPreMortemDTO.builder()
                            .positionId(pos.getId())
                            .symbol(pos.getSymbol())
                            .direction(pos.getDirection())
                            .entryPrice(pos.getEntryPrice())
                            .currentPrice(check.getCurrentPrice())
                            .currentPnlPercent(check.getCurrentPnlPercent())
                            .holdHours(check.getHoldTimeHours())
                            .preMortem(pos.getPreMortem())
                            .bullCase(pos.getBullCase())
                            .bearCase(pos.getBearCase())
                            .expectedHoldHoursMin(pos.getExpectedHoldHoursMin())
                            .expectedHoldHoursMax(pos.getExpectedHoldHoursMax())
                            .status(check.getStatus())
                            .signals(check.getSignals())
                            .build();
                })
                .toList();
        
        return ResponseEntity.ok(results);
    }

    /**
     * Get Pre-Mortem status for a specific position.
     */
    @GetMapping("/positions/{positionId}/premortem-status")
    public ResponseEntity<PositionPreMortemDTO> getPositionPreMortemStatus(
            @PathVariable String positionId) {
        return positionRepository.findById(positionId)
                .map(pos -> {
                    PreMortemCheckResult check = preMortemChecker.checkPreMortem(pos);
                    PositionPreMortemDTO dto = PositionPreMortemDTO.builder()
                            .positionId(pos.getId())
                            .symbol(pos.getSymbol())
                            .direction(pos.getDirection())
                            .entryPrice(pos.getEntryPrice())
                            .currentPrice(check.getCurrentPrice())
                            .currentPnlPercent(check.getCurrentPnlPercent())
                            .holdHours(check.getHoldTimeHours())
                            .preMortem(pos.getPreMortem())
                            .bullCase(pos.getBullCase())
                            .bearCase(pos.getBearCase())
                            .expectedHoldHoursMin(pos.getExpectedHoldHoursMin())
                            .expectedHoldHoursMax(pos.getExpectedHoldHoursMax())
                            .status(check.getStatus())
                            .signals(check.getSignals())
                            .build();
                    return ResponseEntity.ok(dto);
                })
                .orElse(ResponseEntity.notFound().build());
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // INNER CLASSES
    // ═══════════════════════════════════════════════════════════════════════════

    @lombok.Data
    @lombok.Builder
    public static class WisdomSummary {
        private int totalWisdoms;
        private int warningSignals;
        private int blindSpots;
        private int timeLessons;
    }
}

