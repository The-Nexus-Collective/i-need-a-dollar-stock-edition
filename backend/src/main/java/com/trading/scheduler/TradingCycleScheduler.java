package com.trading.scheduler;

import com.trading.service.PortfolioManagerService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/**
 * Trading cycle scheduler - handles timing only.
 * 
 * All business logic is delegated to PortfolioManagerService.
 * This keeps the scheduler focused on a single responsibility:
 * triggering cycles at the configured interval.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TradingCycleScheduler {

    private final PortfolioManagerService portfolioManagerService;

    /**
     * Main trading cycle - runs every 10 minutes by default.
     * Delegates all business logic to PortfolioManagerService.
     */
    @Scheduled(fixedRateString = "${trading.cycle.interval:600000}")
    public void runTradingCycle() {
        PortfolioManagerService.CycleResult result = portfolioManagerService.runCycle();
        
        if (result.isSkipped()) {
            log.debug("Cycle skipped: {}", result.getError());
        } else if (!result.isSuccess()) {
            log.warn("Cycle #{} failed: {}", result.getCycleNumber(), result.getError());
        }
    }

    /**
     * Manually trigger a trading cycle.
     * Returns immediately, cycle runs in background.
     */
    public void triggerManualCycle() {
        new Thread(() -> portfolioManagerService.runCycle()).start();
    }

    /**
     * Check if a cycle is currently running.
     */
    public boolean isRunning() {
        return portfolioManagerService.isRunning();
    }

    /**
     * Get current cycle number.
     */
    public int getCurrentCycleNumber() {
        return portfolioManagerService.getCurrentCycleNumber();
    }
}
