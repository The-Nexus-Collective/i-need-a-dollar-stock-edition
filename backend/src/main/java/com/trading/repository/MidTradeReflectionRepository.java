package com.trading.repository;

import com.trading.entity.MidTradeReflection;
import com.trading.entity.MidTradeReflection.HealthStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;

/**
 * Repository for mid-trade reflection entries.
 */
@Repository
public interface MidTradeReflectionRepository extends JpaRepository<MidTradeReflection, String> {

    /**
     * Find all reflections for a specific position.
     */
    List<MidTradeReflection> findByPositionIdOrderByEvaluatedAtDesc(String positionId);

    /**
     * Find latest reflection for each open position.
     */
    @Query("SELECT m FROM MidTradeReflection m WHERE m.evaluatedAt = " +
           "(SELECT MAX(m2.evaluatedAt) FROM MidTradeReflection m2 WHERE m2.positionId = m.positionId)")
    List<MidTradeReflection> findLatestForEachPosition();

    /**
     * Find reflections by health status.
     */
    List<MidTradeReflection> findByHealthStatusOrderByEvaluatedAtDesc(HealthStatus healthStatus);

    /**
     * Find reflections within a time range.
     */
    List<MidTradeReflection> findByEvaluatedAtBetweenOrderByEvaluatedAtDesc(Instant from, Instant to);

    /**
     * Count reflections by health status.
     */
    long countByHealthStatus(HealthStatus healthStatus);

    /**
     * Count total danger evaluations (for learning stats).
     */
    @Query("SELECT COUNT(m) FROM MidTradeReflection m WHERE m.healthStatus = 'DANGER'")
    long countDangerEvaluations();

    /**
     * Count evaluations where action was taken.
     */
    @Query("SELECT COUNT(m) FROM MidTradeReflection m WHERE m.actionTaken IS NOT NULL")
    long countWithActionTaken();

    /**
     * Find reflections where recommendation was CLOSE_RECOMMENDED.
     */
    List<MidTradeReflection> findByRecommendationOrderByEvaluatedAtDesc(String recommendation);

    /**
     * Get recent reflections for timeline display.
     */
    List<MidTradeReflection> findTop50ByOrderByEvaluatedAtDesc();

    /**
     * Find reflections for a specific cycle.
     */
    List<MidTradeReflection> findByCycleNumberOrderByEvaluatedAtDesc(Integer cycleNumber);

    /**
     * Count how many times Pre-Mortem warnings were correct (position later closed at loss).
     */
    @Query("SELECT COUNT(m) FROM MidTradeReflection m WHERE m.healthStatus = 'DANGER' " +
           "AND m.actionTaken = 'CLOSED' AND m.withinPnlExpectations = false")
    long countCorrectDangerPredictions();
}

