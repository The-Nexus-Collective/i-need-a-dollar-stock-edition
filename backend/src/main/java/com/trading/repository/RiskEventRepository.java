package com.trading.repository;

import com.trading.entity.RiskEvent;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Repository for RiskEvent entities
 */
@Repository
public interface RiskEventRepository extends JpaRepository<RiskEvent, UUID> {

    /**
     * Find recent risk events
     */
    List<RiskEvent> findByOrderByTimestampDesc(Pageable pageable);

    /**
     * Find by severity
     */
    List<RiskEvent> findBySeverityOrderByTimestampDesc(String severity);

    /**
     * Find by event type
     */
    List<RiskEvent> findByEventTypeOrderByTimestampDesc(String eventType);
    
    /**
     * Find by event type with pagination
     */
    List<RiskEvent> findByEventTypeOrderByTimestampDesc(String eventType, Pageable pageable);
    
    /**
     * Count by event type
     */
    long countByEventType(String eventType);

    /**
     * Find unacknowledged events
     */
    List<RiskEvent> findByAcknowledgedFalseOrderByTimestampDesc();

    /**
     * Find events since timestamp
     */
    @Query("SELECT r FROM RiskEvent r WHERE r.timestamp >= :since ORDER BY r.timestamp DESC")
    List<RiskEvent> findEventsSince(@Param("since") Instant since);

    /**
     * Count by severity
     */
    long countBySeverity(String severity);
}

