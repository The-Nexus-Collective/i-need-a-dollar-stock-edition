package com.inad.stocks.scheduler;

import com.inad.stocks.service.FundingService;
import com.inad.stocks.service.MarketHoursService;
import com.inad.stocks.service.PortfolioManagerService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/**
 * Trading cycle scheduler - handles timing only.
 * 
 * Responsibilities:
 * - Trading cycles: Triggered at configured interval (only when market is open)
 * - Funding payments: Triggered at 00:00, 08:00, 16:00 UTC (Binance schedule)
 * 
 * Market Hours Enforcement:
 * - NYSE/NASDAQ: 09:30 - 16:00 ET on business days
 * - Trading is blocked on weekends and US market holidays
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TradingCycleScheduler {

    private final PortfolioManagerService portfolioManagerService;
    private final FundingService fundingService;
    private final MarketHoursService marketHoursService;

    /**
     * Main trading cycle - runs every 10 minutes by default.
     * Only executes if the market is open.
     * Delegates all business logic to PortfolioManagerService.
     */
    @Scheduled(fixedRateString = "${trading.cycle.interval:600000}")
    public void runTradingCycle() {
        // Quick check - market hours check is also in PortfolioManagerService but log here for visibility
        if (!marketHoursService.isTradingAllowed()) {
            MarketHoursService.MarketStatus status = marketHoursService.getMarketStatus();
            log.debug("Scheduled cycle skipped - market closed: {} ({})", 
                    status.status(), status.detail());
            return;
        }
        
        PortfolioManagerService.CycleResult result = portfolioManagerService.runCycle();
        
        if (result.isSkipped()) {
            if (result.isMarketClosed()) {
                log.debug("Cycle skipped - market closed: {}", result.getError());
            } else {
                log.debug("Cycle skipped: {}", result.getError());
            }
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
