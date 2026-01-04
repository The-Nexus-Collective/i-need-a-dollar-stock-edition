package com.trading.repository;

import com.trading.entity.PortfolioSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Repository for PortfolioSnapshot entities
 */
@Repository
public interface PortfolioSnapshotRepository extends JpaRepository<PortfolioSnapshot, Instant> {

    /**
     * Find snapshots since timestamp
     */
    @Query("SELECT p FROM PortfolioSnapshot p WHERE p.timestamp >= :since ORDER BY p.timestamp ASC")
    List<PortfolioSnapshot> findSnapshotsSince(@Param("since") Instant since);

    /**
     * Find latest snapshot
     */
    @Query("SELECT p FROM PortfolioSnapshot p ORDER BY p.timestamp DESC LIMIT 1")
    Optional<PortfolioSnapshot> findLatest();

    /**
     * Find snapshots between timestamps (for equity curve)
     */
    @Query("SELECT p FROM PortfolioSnapshot p WHERE p.timestamp BETWEEN :start AND :end ORDER BY p.timestamp ASC")
    List<PortfolioSnapshot> findBetween(@Param("start") Instant start, @Param("end") Instant end);

    /**
     * Delete old snapshots (retention policy)
     */
    void deleteByTimestampBefore(Instant before);
}

