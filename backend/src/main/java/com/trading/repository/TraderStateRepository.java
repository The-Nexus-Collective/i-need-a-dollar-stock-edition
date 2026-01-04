package com.trading.repository;

import com.trading.entity.TraderState;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * Repository for TraderState entity (singleton)
 */
@Repository
public interface TraderStateRepository extends JpaRepository<TraderState, String> {

    /**
     * Get the main trader state
     */
    default Optional<TraderState> findMain() {
        return findById("main");
    }

    /**
     * Get or create the main trader state
     */
    default TraderState getOrCreateMain() {
        return findById("main").orElseGet(() -> {
            TraderState state = TraderState.builder().id("main").build();
            return save(state);
        });
    }
}

