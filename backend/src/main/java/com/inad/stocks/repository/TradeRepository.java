package com.inad.stocks.repository;

import com.inad.stocks.entity.Trade;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

/**
 * Repository for Trade entities
 */
@Repository
public interface TradeRepository extends JpaRepository<Trade, String> {

    /**
     * Find recent trades ordered by exit time
     */
    List<Trade> findByOrderByExitTimeDesc(Pageable pageable);

    /**
     * Find trades since a given timestamp
     */
    @Query("SELECT t FROM Trade t WHERE t.exitTime >= :since ORDER BY t.exitTime DESC")
    List<Trade> findTradesSince(@Param("since") Instant since);

    /**
     * Find trades for a specific symbol
     */
    List<Trade> findBySymbolOrderByExitTimeDesc(String symbol);

    /**
     * Calculate total PnL
     */
    @Query("SELECT COALESCE(SUM(t.pnlUsd), 0) FROM Trade t")
    BigDecimal calculateTotalPnl();

    /**
     * Calculate total PnL since timestamp
     */
    @Query("SELECT COALESCE(SUM(t.pnlUsd), 0) FROM Trade t WHERE t.exitTime >= :since")
    BigDecimal calculatePnlSince(@Param("since") Instant since);

    /**
     * Count winning trades
     */
    @Query("SELECT COUNT(t) FROM Trade t WHERE t.pnlUsd > 0")
    int countWinningTrades();

    /**
     * Count losing trades
     */
    @Query("SELECT COUNT(t) FROM Trade t WHERE t.pnlUsd < 0")
    int countLosingTrades();

    /**
     * Find trades by exit reason
     */
    List<Trade> findByExitReasonOrderByExitTimeDesc(String exitReason);

    /**
     * Calculate average PnL percent
     */
    @Query("SELECT AVG(t.pnlPercent) FROM Trade t")
    BigDecimal calculateAveragePnlPercent();
}

