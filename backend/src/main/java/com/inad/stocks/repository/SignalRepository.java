package com.inad.stocks.repository;

import com.inad.stocks.entity.Signal;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Repository for Signal entities
 */
@Repository
public interface SignalRepository extends JpaRepository<Signal, UUID> {

    /**
     * Find recent signals
     */
    List<Signal> findByOrderByTimestampDesc(Pageable pageable);

    /**
     * Find signals since timestamp
     */
    @Query("SELECT s FROM Signal s WHERE s.timestamp >= :since ORDER BY s.timestamp DESC")
    List<Signal> findSignalsSince(@Param("since") Instant since);

    /**
     * Find signals for a symbol
     */
    List<Signal> findBySymbolOrderByTimestampDesc(String symbol);

    /**
     * Find executed signals
     */
    List<Signal> findByExecutedTrueOrderByTimestampDesc();

    /**
     * Find risk-approved signals
     */
    List<Signal> findByRiskApprovedTrueOrderByTimestampDesc();

    /**
     * Find signals by recommended action
     */
    List<Signal> findByRecommendedActionOrderByTimestampDesc(String action);
}

