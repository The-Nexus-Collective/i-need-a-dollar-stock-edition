package com.inad.stocks.repository;

import com.inad.stocks.entity.ReflectionEntry;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;

/**
 * Repository for ReflectionEntry entities.
 */
@Repository
public interface ReflectionEntryRepository extends JpaRepository<ReflectionEntry, String> {

    /**
     * Find recent reflections ordered by time (newest first).
     */
    List<ReflectionEntry> findAllByOrderByReflectedAtDesc();

    /**
     * Find top N recent reflections.
     */
    @Query("SELECT r FROM ReflectionEntry r ORDER BY r.reflectedAt DESC")
    List<ReflectionEntry> findTopByOrderByReflectedAtDesc(Pageable pageable);

    /**
     * Find reflections where Pre-Mortem was correct.
     */
    List<ReflectionEntry> findByPreMortemWasCorrectTrueOrderByReflectedAtDesc();

    /**
     * Find reflections where Pre-Mortem was incorrect (blind spots identified).
     */
    List<ReflectionEntry> findByPreMortemWasCorrectFalseOrderByReflectedAtDesc();

    /**
     * Count reflections where Pre-Mortem was correct.
     */
    long countByPreMortemWasCorrectTrue();

    /**
     * Count reflections where Pre-Mortem was incorrect.
     */
    long countByPreMortemWasCorrectFalse();

    /**
     * Find reflections for a specific position.
     */
    List<ReflectionEntry> findByPositionIdOrderByReflectedAtDesc(String positionId);

    /**
     * Find reflections for a specific symbol.
     */
    List<ReflectionEntry> findBySymbolOrderByReflectedAtDesc(String symbol);

    /**
     * Find reflections after a certain time.
     */
    @Query("SELECT r FROM ReflectionEntry r WHERE r.reflectedAt > :since ORDER BY r.reflectedAt DESC")
    List<ReflectionEntry> findReflectionsSince(@Param("since") Instant since);

    /**
     * Count total reflections.
     */
    @Query("SELECT COUNT(r) FROM ReflectionEntry r")
    long countTotalReflections();
}

