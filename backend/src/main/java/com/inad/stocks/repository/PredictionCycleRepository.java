package com.inad.stocks.repository;

import com.inad.stocks.entity.PredictionCycle;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * Repository for PredictionCycle entities
 */
@Repository
public interface PredictionCycleRepository extends JpaRepository<PredictionCycle, UUID> {

    /**
     * Find recent cycles
     */
    List<PredictionCycle> findByOrderByStartedAtDesc(Pageable pageable);

    /**
     * Find running cycle
     */
    Optional<PredictionCycle> findByStatus(String status);

    /**
     * Find latest completed cycle
     */
    @Query("SELECT c FROM PredictionCycle c WHERE c.status = 'completed' ORDER BY c.completedAt DESC LIMIT 1")
    Optional<PredictionCycle> findLatestCompleted();

    /**
     * Get the highest cycle number
     */
    @Query("SELECT MAX(c.cycleNumber) FROM PredictionCycle c")
    Optional<Integer> findMaxCycleNumber();
}

