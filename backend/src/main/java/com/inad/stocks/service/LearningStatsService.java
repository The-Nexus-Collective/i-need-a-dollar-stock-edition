package com.inad.stocks.service;

import com.inad.stocks.entity.MidTradeReflection;
import com.inad.stocks.entity.ReflectionEntry;
import com.inad.stocks.entity.Trade;
import com.inad.stocks.entity.TradeWisdom;
import com.inad.stocks.entity.TradeWisdom.WisdomType;
import com.inad.stocks.repository.MidTradeReflectionRepository;
import com.inad.stocks.repository.ReflectionEntryRepository;
import com.inad.stocks.repository.TradeRepository;
import com.inad.stocks.repository.TradeWisdomRepository;
import org.springframework.beans.factory.annotation.Autowired;
import lombok.Builder;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Service to calculate learning effectiveness statistics.
 * 
 * Provides metrics to evaluate if the self-learning system is working:
 * - Pre-Mortem accuracy
 * - Win rate before vs after learning
 * - Impact of following learned wisdom
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class LearningStatsService {

    private final ReflectionEntryRepository reflectionRepository;
    private final TradeRepository tradeRepository;
    private final TradeWisdomRepository wisdomRepository;
    
    @Autowired(required = false)
    private MidTradeReflectionRepository midTradeReflectionRepository;

    @Data
    @Builder
    public static class LearningStats {
        private int totalReflections;
        private int correctPreMortems;
        private BigDecimal preMortemAccuracyPercent;

        private BigDecimal winRateBeforeLearning;
        private BigDecimal winRateWithLearning;
        private BigDecimal avgPnlBeforeLearning;
        private BigDecimal avgPnlWithLearning;

        private int totalWisdoms;
        private int warningSignals;
        private int blindSpots;
        private int timeLessons;

        private BigDecimal winRateImprovement;
        private BigDecimal avgPnlImprovement;
        private boolean learningEffective;
        
        // Mid-trade reflection stats
        private int totalMidTradeEvaluations;
        private int midTradeDangerCount;
        private int midTradeWarningCount;
        private int midTradeHealthyCount;
        private BigDecimal dangerWarningRate;  // % of evaluations that were DANGER or WARNING
    }

    /**
     * Calculate comprehensive learning statistics.
     */
    public LearningStats calculateStats() {
        // Get all reflections
        List<ReflectionEntry> reflections = reflectionRepository.findAll();
        int totalReflections = reflections.size();
        
        int correctPreMortems = (int) reflections.stream()
                .filter(r -> r.getPreMortemWasCorrect() != null && r.getPreMortemWasCorrect())
                .count();

        BigDecimal preMortemAccuracy = totalReflections > 0
                ? BigDecimal.valueOf(correctPreMortems * 100.0 / totalReflections)
                        .setScale(1, RoundingMode.HALF_UP)
                : BigDecimal.ZERO;

        // Find when learning started
        Optional<TradeWisdom> firstWisdom = wisdomRepository.findFirstByOrderByFirstOccurredAsc();
        Instant learningStarted = firstWisdom.map(TradeWisdom::getFirstOccurred).orElse(Instant.now());

        // Get all trades
        List<Trade> allTrades = tradeRepository.findAll();
        
        // Split trades before and after learning
        List<Trade> tradesBeforeLearning = allTrades.stream()
                .filter(t -> t.getExitTime() != null && t.getExitTime().isBefore(learningStarted))
                .toList();
        
        List<Trade> tradesWithLearning = allTrades.stream()
                .filter(t -> t.getExitTime() != null && t.getExitTime().isAfter(learningStarted))
                .toList();

        // Calculate win rates
        BigDecimal winRateBefore = calculateWinRate(tradesBeforeLearning);
        BigDecimal winRateWith = calculateWinRate(tradesWithLearning);

        // Calculate average PnL
        BigDecimal avgPnlBefore = calculateAvgPnlPercent(tradesBeforeLearning);
        BigDecimal avgPnlWith = calculateAvgPnlPercent(tradesWithLearning);

        // Calculate improvements
        BigDecimal winRateImprovement = winRateWith.subtract(winRateBefore);
        BigDecimal avgPnlImprovement = avgPnlWith.subtract(avgPnlBefore);

        // Count wisdoms by type
        int warningSignals = (int) wisdomRepository.countByType(WisdomType.WARNING_SIGNAL);
        int blindSpots = (int) wisdomRepository.countByType(WisdomType.BLIND_SPOT);
        int timeLessons = (int) wisdomRepository.countByType(WisdomType.TIME_LESSON);
        int totalWisdoms = warningSignals + blindSpots + timeLessons;

        // Determine if learning is effective
        boolean learningEffective = winRateImprovement.compareTo(BigDecimal.ZERO) > 0 ||
                avgPnlImprovement.compareTo(BigDecimal.ZERO) > 0;

        // Calculate mid-trade reflection stats
        int totalMidTrade = 0;
        int midTradeDanger = 0;
        int midTradeWarning = 0;
        int midTradeHealthy = 0;
        BigDecimal dangerWarningRate = BigDecimal.ZERO;
        
        if (midTradeReflectionRepository != null) {
            List<MidTradeReflection> midTradeReflections = midTradeReflectionRepository.findAll();
            totalMidTrade = midTradeReflections.size();
            
            midTradeDanger = (int) midTradeReflections.stream()
                    .filter(r -> r.getHealthStatus() == MidTradeReflection.HealthStatus.DANGER)
                    .count();
            midTradeWarning = (int) midTradeReflections.stream()
                    .filter(r -> r.getHealthStatus() == MidTradeReflection.HealthStatus.WARNING)
                    .count();
            midTradeHealthy = (int) midTradeReflections.stream()
                    .filter(r -> r.getHealthStatus() == MidTradeReflection.HealthStatus.HEALTHY)
                    .count();
            
            if (totalMidTrade > 0) {
                dangerWarningRate = BigDecimal.valueOf((midTradeDanger + midTradeWarning) * 100.0 / totalMidTrade)
                        .setScale(1, RoundingMode.HALF_UP);
            }
        }

        return LearningStats.builder()
                .totalReflections(totalReflections)
                .correctPreMortems(correctPreMortems)
                .preMortemAccuracyPercent(preMortemAccuracy)
                .winRateBeforeLearning(winRateBefore)
                .winRateWithLearning(winRateWith)
                .avgPnlBeforeLearning(avgPnlBefore)
                .avgPnlWithLearning(avgPnlWith)
                .totalWisdoms(totalWisdoms)
                .warningSignals(warningSignals)
                .blindSpots(blindSpots)
                .timeLessons(timeLessons)
                .winRateImprovement(winRateImprovement)
                .avgPnlImprovement(avgPnlImprovement)
                .learningEffective(learningEffective)
                // Mid-trade stats
                .totalMidTradeEvaluations(totalMidTrade)
                .midTradeDangerCount(midTradeDanger)
                .midTradeWarningCount(midTradeWarning)
                .midTradeHealthyCount(midTradeHealthy)
                .dangerWarningRate(dangerWarningRate)
                .build();
    }

    /**
     * Calculate win rate for a list of trades.
     */
    private BigDecimal calculateWinRate(List<Trade> trades) {
        if (trades.isEmpty()) {
            return BigDecimal.ZERO;
        }

        long winners = trades.stream()
                .filter(t -> t.getPnlUsd() != null && t.getPnlUsd().compareTo(BigDecimal.ZERO) > 0)
                .count();

        return BigDecimal.valueOf(winners * 100.0 / trades.size())
                .setScale(1, RoundingMode.HALF_UP);
    }

    /**
     * Calculate average PnL percentage for a list of trades.
     */
    private BigDecimal calculateAvgPnlPercent(List<Trade> trades) {
        if (trades.isEmpty()) {
            return BigDecimal.ZERO;
        }

        BigDecimal totalPnlPercent = trades.stream()
                .filter(t -> t.getPnlPercent() != null)
                .map(Trade::getPnlPercent)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        return totalPnlPercent.divide(BigDecimal.valueOf(trades.size()), 2, RoundingMode.HALF_UP);
    }

    /**
     * Get count of trades with Pre-Mortem data.
     */
    public long getTradesWithPreMortem() {
        return reflectionRepository.countTotalReflections();
    }

    /**
     * Get Pre-Mortem accuracy for losing trades specifically.
     */
    public BigDecimal getPreMortemAccuracyForLosers() {
        List<ReflectionEntry> losingReflections = reflectionRepository.findAll().stream()
                .filter(r -> r.getPnlPercent() != null && r.getPnlPercent().compareTo(BigDecimal.ZERO) < 0)
                .toList();

        if (losingReflections.isEmpty()) {
            return BigDecimal.ZERO;
        }

        long correct = losingReflections.stream()
                .filter(r -> r.getPreMortemWasCorrect() != null && r.getPreMortemWasCorrect())
                .count();

        return BigDecimal.valueOf(correct * 100.0 / losingReflections.size())
                .setScale(1, RoundingMode.HALF_UP);
    }

    /**
     * Get recent mid-trade reflections for display.
     */
    public List<MidTradeReflection> getRecentMidTradeReflections(int limit) {
        if (midTradeReflectionRepository == null) {
            return List.of();
        }
        return midTradeReflectionRepository.findTop50ByOrderByEvaluatedAtDesc().stream()
                .limit(limit)
                .toList();
    }

    /**
     * Get mid-trade reflections for a specific position.
     */
    public List<MidTradeReflection> getMidTradeReflectionsForPosition(String positionId) {
        if (midTradeReflectionRepository == null) {
            return List.of();
        }
        return midTradeReflectionRepository.findByPositionIdOrderByEvaluatedAtDesc(positionId);
    }

    /**
     * Calculate how accurate DANGER warnings are at predicting losses.
     * Tracks when a DANGER mid-trade reflection was followed by actual position loss.
     */
    public BigDecimal getMidTradeDangerAccuracy() {
        if (midTradeReflectionRepository == null) {
            return BigDecimal.ZERO;
        }
        
        // Get all DANGER reflections that resulted in action
        List<MidTradeReflection> dangerReflections = midTradeReflectionRepository
                .findByRecommendationOrderByEvaluatedAtDesc("CLOSE_RECOMMENDED");
        
        if (dangerReflections.isEmpty()) {
            return BigDecimal.ZERO;
        }
        
        long correct = midTradeReflectionRepository.countCorrectDangerPredictions();
        
        return BigDecimal.valueOf(correct * 100.0 / dangerReflections.size())
                .setScale(1, RoundingMode.HALF_UP);
    }
}

