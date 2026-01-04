package com.trading.repository;

import com.trading.entity.LogbookEntry;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * Repository for logbook entries.
 */
@Repository
public interface LogbookRepository extends JpaRepository<LogbookEntry, String> {
    
    /**
     * Get latest entries, ordered by timestamp descending.
     */
    List<LogbookEntry> findAllByOrderByTimestampDesc();
    
    /**
     * Get latest N entries.
     */
    List<LogbookEntry> findTop50ByOrderByTimestampDesc();
    
    /**
     * Find by cycle number.
     */
    Optional<LogbookEntry> findByCycleNumber(int cycleNumber);
    
    /**
     * Get the maximum cycle number.
     */
    @Query("SELECT COALESCE(MAX(e.cycleNumber), 0) FROM LogbookEntry e")
    int getMaxCycleNumber();
    
    /**
     * Count all entries.
     */
    long count();
    
    /**
     * Delete all entries (for reset).
     */
    @Modifying
    @Query("DELETE FROM LogbookEntry")
    void deleteAllEntries();
    
    /**
     * Search entries by analysis text.
     */
    @Query("SELECT e FROM LogbookEntry e WHERE LOWER(e.analysisText) LIKE LOWER(CONCAT('%', :query, '%')) ORDER BY e.timestamp DESC")
    List<LogbookEntry> searchByAnalysisText(String query);
    
    /**
     * Get total tokens used.
     */
    @Query("SELECT COALESCE(SUM(e.tokensUsed), 0) FROM LogbookEntry e")
    long sumTokensUsed();
}

