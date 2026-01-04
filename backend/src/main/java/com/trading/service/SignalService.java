package com.trading.service;

import com.trading.entity.Signal;
import com.trading.repository.SignalRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;

/**
 * Service for trading signals
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SignalService {

    private final SignalRepository signalRepository;

    /**
     * Get recent signals
     */
    public List<Signal> getRecentSignals(int limit) {
        return signalRepository.findByOrderByTimestampDesc(PageRequest.of(0, limit));
    }

    /**
     * Get signals since timestamp
     */
    public List<Signal> getSignalsSince(Instant since) {
        return signalRepository.findSignalsSince(since);
    }

    /**
     * Get signals for a coin
     */
    public List<Signal> getSignalsForCoin(String coin) {
        return signalRepository.findByCoinOrderByTimestampDesc(coin);
    }

    /**
     * Get executed signals
     */
    public List<Signal> getExecutedSignals() {
        return signalRepository.findByExecutedTrueOrderByTimestampDesc();
    }
}

