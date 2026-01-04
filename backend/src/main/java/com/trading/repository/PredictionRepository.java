package com.trading.repository;

import com.trading.entity.Prediction;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

/**
 * Repository for Prediction entities
 */
@Repository
public interface PredictionRepository extends JpaRepository<Prediction, UUID> {

    /**
     * Find predictions for a cycle
     */
    List<Prediction> findByCycleIdOrderByCreatedAtDesc(UUID cycleId);

    /**
     * Find recent predictions
     */
    List<Prediction> findByOrderByCreatedAtDesc(Pageable pageable);

    /**
     * Find predictions for a coin
     */
    List<Prediction> findByCoinOrderByCreatedAtDesc(String coin);

    /**
     * Find winning predictions
     */
    @Query("SELECT p FROM Prediction p WHERE p.pnl > 0 ORDER BY p.createdAt DESC")
    List<Prediction> findWinningPredictions(Pageable pageable);

    /**
     * Count predictions by direction
     */
    long countByDirection(String direction);
}

