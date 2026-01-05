package com.inad.stocks.repository;

import com.inad.stocks.entity.Prediction;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
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
     * Find predictions for a symbol
     */
    List<Prediction> findBySymbolOrderByCreatedAtDesc(String symbol);

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

