package com.inad.stocks.repository;

import com.inad.stocks.entity.TradeWisdom;
import com.inad.stocks.entity.TradeWisdom.WisdomType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Repository for TradeWisdom entities.
 */
@Repository
public interface TradeWisdomRepository extends JpaRepository<TradeWisdom, String> {

    /**
     * Find all wisdoms ordered by occurrence count (most frequent first).
     */
    List<TradeWisdom> findAllByOrderByOccurrencesDesc();

    /**
     * Find wisdoms by type ordered by occurrence count.
     */
    List<TradeWisdom> findByTypeOrderByOccurrencesDesc(WisdomType type);

    /**
     * Find top N wisdoms of a specific type.
     */
    @Query("SELECT w FROM TradeWisdom w WHERE w.type = :type ORDER BY w.occurrences DESC LIMIT :limit")
    List<TradeWisdom> findTopByTypeOrderByOccurrencesDesc(@Param("type") WisdomType type, @Param("limit") int limit);

    /**
     * Find the first wisdom created (for determining when learning started).
     */
    Optional<TradeWisdom> findFirstByOrderByFirstOccurredAsc();

    /**
     * Count wisdoms by type.
     */
    long countByType(WisdomType type);

    /**
     * Find wisdom by description (for deduplication).
     */
    @Query("SELECT w FROM TradeWisdom w WHERE LOWER(w.description) LIKE LOWER(CONCAT('%', :description, '%'))")
    List<TradeWisdom> findByDescriptionContaining(@Param("description") String description);

    /**
     * Find wisdoms related to a specific symbol pattern.
     */
    List<TradeWisdom> findBySymbolPatternOrderByOccurrencesDesc(String symbolPattern);

    /**
     * Find wisdoms by direction pattern (LONG/SHORT).
     */
    List<TradeWisdom> findByDirectionPatternOrderByOccurrencesDesc(String directionPattern);
}

