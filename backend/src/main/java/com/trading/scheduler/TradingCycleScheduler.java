package com.trading.scheduler;

import com.trading.service.FundingService;
import com.trading.service.PortfolioManagerService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/**
 * Trading cycle scheduler - handles timing only.
 * 
 * Responsibilities:
 * - Trading cycles: Triggered at configured interval
 * - Funding payments: Triggered at 00:00, 08:00, 16:00 UTC (Binance schedule)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TradingCycleScheduler {

    private final PortfolioManagerService portfolioManagerService;
    private final FundingService fundingService;

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

    /**
     * Process funding payments at Binance funding times.
     * Runs at 00:00, 08:00, 16:00 UTC (every 8 hours).
     * 
     * Funding is exchanged between long and short position holders
     * based on the current funding rate for each symbol.
     */
    @Scheduled(cron = "0 0 0,8,16 * * *", zone = "UTC")
    public void processFundingPayments() {
        log.info("Processing 8-hourly funding payments...");
        try {
            FundingService.FundingResult result = fundingService.processFundingPayments();
            log.info("Funding complete: {} positions processed, {} failed, net {} USDT",
                    result.positionsProcessed(),
                    result.positionsFailed(),
                    result.netFunding());
        } catch (Exception e) {
            log.error("Failed to process funding payments: {}", e.getMessage(), e);
        }
    }

    /**
     * Manually trigger funding processing (for testing).
     */
    public FundingService.FundingResult triggerManualFunding() {
        return fundingService.processFundingPayments();
    }
}
