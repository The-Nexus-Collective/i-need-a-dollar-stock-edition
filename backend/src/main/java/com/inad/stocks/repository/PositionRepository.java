package com.inad.stocks.repository;

import com.inad.stocks.entity.Position;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Repository for Position entities
 */
@Repository
public interface PositionRepository extends JpaRepository<Position, String> {

    /**
     * Find all open positions
     */
    @Query("SELECT p FROM Position p WHERE p.status = 'OPEN' ORDER BY p.entryTime DESC")
    List<Position> findOpenPositions();

    /**
     * Find closed positions ordered by exit time
     */
    @Query("SELECT p FROM Position p WHERE p.status != 'OPEN' ORDER BY p.exitTime DESC")
    List<Position> findClosedPositions();

    /**
     * Find position by symbol with OPEN status
     */
    @Query("SELECT p FROM Position p WHERE p.symbol = :symbol AND p.status = 'OPEN'")
    Optional<Position> findOpenPositionBySymbol(@Param("symbol") String symbol);

    /**
     * Count open positions
     */
    @Query("SELECT COUNT(p) FROM Position p WHERE p.status = 'OPEN'")
    int countOpenPositions();

    /**
     * Find positions by status
     */
    List<Position> findByStatusOrderByEntryTimeDesc(String status);

    /**
     * Find recent positions (open or recently closed)
     */
    @Query("SELECT p FROM Position p WHERE p.status = 'OPEN' OR p.exitTime > :since ORDER BY p.entryTime DESC")
    List<Position> findRecentPositions(@Param("since") java.time.Instant since);

    /**
     * Find all positions for a symbol
     */
    List<Position> findBySymbolOrderByEntryTimeDesc(String symbol);
}

