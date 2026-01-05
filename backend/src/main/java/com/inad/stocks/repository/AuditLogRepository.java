package com.inad.stocks.repository;

import com.inad.stocks.entity.AuditLog;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;

/**
 * Repository for AuditLog entities
 */
@Repository
public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {

    /**
     * Find recent audit entries
     */
    List<AuditLog> findByOrderByTimestampDesc(Pageable pageable);

    /**
     * Find by event type
     */
    List<AuditLog> findByEventTypeOrderByTimestampDesc(String eventType);

    /**
     * Find by actor
     */
    List<AuditLog> findByActorOrderByTimestampDesc(String actor);

    /**
     * Find by entity
     */
    @Query("SELECT a FROM AuditLog a WHERE a.entityType = :entityType AND a.entityId = :entityId ORDER BY a.timestamp DESC")
    List<AuditLog> findByEntity(@Param("entityType") String entityType, @Param("entityId") String entityId);

    /**
     * Find entries since timestamp
     */
    @Query("SELECT a FROM AuditLog a WHERE a.timestamp >= :since ORDER BY a.timestamp DESC")
    List<AuditLog> findSince(@Param("since") Instant since);

    /**
     * Get the last audit log for hash chaining
     */
    @Query("SELECT a FROM AuditLog a ORDER BY a.id DESC LIMIT 1")
    java.util.Optional<AuditLog> findLast();
}

