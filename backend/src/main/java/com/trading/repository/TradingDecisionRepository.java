package com.trading.repository;

import com.trading.entity.TradingDecision;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Repository for TradingDecision entities
 */
@Repository
public interface TradingDecisionRepository extends JpaRepository<TradingDecision, UUID> {

    /**
     * Find recent decisions
     */
    List<TradingDecision> findByOrderByCreatedAtDesc(Pageable pageable);

    /**
     * Find by decision type
     */
    List<TradingDecision> findByDecisionOrderByCreatedAtDesc(String decision);

    /**
     * Find executed decisions
     */
    List<TradingDecision> findByWasExecutedTrueOrderByCreatedAtDesc();

    /**
     * Find decisions for a coin
     */
    List<TradingDecision> findByCoinOrderByCreatedAtDesc(String coin);

    /**
     * Find decisions since timestamp
     */
    @Query("SELECT d FROM TradingDecision d WHERE d.createdAt >= :since ORDER BY d.createdAt DESC")
    List<TradingDecision> findDecisionsSince(@Param("since") Instant since);
}

