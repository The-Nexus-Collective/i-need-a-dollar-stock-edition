package com.inad.stocks.controller;

import com.inad.stocks.dto.PortfolioResponse;
import com.inad.stocks.dto.PositionDTO;
import com.inad.stocks.scheduler.TradingCycleScheduler;
import com.inad.stocks.service.MarketHoursService;
import com.inad.stocks.service.PortfolioManagerService;
import com.inad.stocks.service.PortfolioService;
import com.inad.stocks.service.PositionService;
import com.inad.stocks.websocket.EquityWebSocketHandler;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Portfolio API endpoints
 */
@Slf4j
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class PortfolioController {

    private final PortfolioService portfolioService;
    private final PositionService positionService;
    private final EquityWebSocketHandler equityWebSocketHandler;
    private final TradingCycleScheduler tradingCycleScheduler;
    private final MarketHoursService marketHoursService;
    private final PortfolioManagerService portfolioManagerService;

    @Value("${trading.capital.starting:0}")
    private BigDecimal startingCapital;

    @Value("${trading.deployment.min-ratio:0.75}")
    private BigDecimal minDeploymentRatio;

    @GetMapping("/portfolio")
    public PortfolioResponse getPortfolio() {
        return portfolioService.getPortfolio();
    }

    @DeleteMapping("/paper-trades/reset")
    public ResponseEntity<Map<String, Object>> resetPaperTrades() {
        portfolioService.resetPaperTrades(startingCapital);
        
        // Notify WebSocket clients
        equityWebSocketHandler.broadcastReset();
        
        return ResponseEntity.ok(Map.of(
                "message", "Paper trades reset successfully",
                "initial_capital", startingCapital
        ));
    }

    @GetMapping("/portfolio-manager/status")
    public Map<String, Object> getPortfolioManagerStatus() {
        PortfolioResponse portfolio = portfolioService.getPortfolio();
        
        // Get actual open positions
        List<PositionDTO> openPositions = positionService.getOpenPositions();
        log.info("getPortfolioManagerStatus: Found {} open positions", openPositions.size());
        
        // Calculate deployment metrics
        BigDecimal totalDeployed = openPositions.stream()
                .map(PositionDTO::getSizeUsd)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        BigDecimal totalEquity = portfolio.getTotalEquity();
        BigDecimal deploymentRatio = totalEquity.compareTo(BigDecimal.ZERO) > 0
                ? totalDeployed.divide(totalEquity, 4, java.math.RoundingMode.HALF_UP)
                : BigDecimal.ZERO;
        BigDecimal deploymentPercent = deploymentRatio.multiply(BigDecimal.valueOf(100));
        boolean belowMinimum = deploymentRatio.compareTo(minDeploymentRatio) < 0;
        BigDecimal capitalToDeploy = belowMinimum 
                ? totalEquity.multiply(minDeploymentRatio).subtract(totalDeployed)
                : BigDecimal.ZERO;
        
        // Build deployment object
        Map<String, Object> deployment = Map.of(
                "total_deployed", totalDeployed,
                "deployment_ratio", deploymentRatio,
                "deployment_percent", deploymentPercent,
                "below_minimum", belowMinimum,
                "capital_to_deploy", capitalToDeploy
        );
        
        // Return format expected by frontend: portfolio.statistics and portfolio.positions
        Map<String, Object> statistics = new HashMap<>();
        statistics.put("starting_capital", portfolio.getInitialCapital());
        statistics.put("current_capital", portfolio.getCash());
        statistics.put("total_equity", portfolio.getTotalEquity());
        statistics.put("unrealized_pnl", portfolio.getUnrealizedPnl());
        statistics.put("realized_pnl", portfolio.getRealizedPnl());
        statistics.put("total_pnl", portfolio.getTotalPnl());
        statistics.put("open_positions", portfolio.getOpenPositions());
        // Position count is determined dynamically by Grok AI - no artificial limits
        statistics.put("total_trades", portfolio.getTotalTrades());
        statistics.put("winning_trades", portfolio.getWinningTrades());
        statistics.put("losing_trades", portfolio.getLosingTrades());
        statistics.put("win_rate", portfolio.getWinRate());
        statistics.put("total_fees", portfolio.getTotalFees());
        statistics.put("total_spread", portfolio.getTotalSpread());
        statistics.put("total_slippage", portfolio.getTotalSlippage());
        statistics.put("deployment", deployment);
        
        Map<String, Object> portfolioData = new HashMap<>();
        portfolioData.put("positions", openPositions);
        portfolioData.put("statistics", statistics);
        
        // Get market status
        MarketHoursService.MarketStatus marketStatus = marketHoursService.getDetailedMarketStatus();
        Map<String, Object> marketData = new HashMap<>();
        marketData.put("status", marketStatus.status());
        marketData.put("description", marketStatus.description());
        marketData.put("detail", marketStatus.detail());
        marketData.put("is_open", marketStatus.isOpen());
        marketData.put("trading_allowed", marketStatus.isTradingAllowed());
        marketData.put("seconds_until_open", marketStatus.secondsUntilOpen());
        marketData.put("seconds_until_close", marketStatus.secondsUntilClose());
        if (marketStatus.nextOpen() != null) {
            marketData.put("next_open", marketStatus.nextOpen().toString());
        }
        if (marketStatus.nextOpenDisplay() != null) {
            marketData.put("next_open_display", marketStatus.nextOpenDisplay());
        }
        marketData.put("data_source", marketStatus.dataSource());
        
        Map<String, Object> result = new HashMap<>();
        result.put("status", "running");
        result.put("mode", "paper");
        result.put("portfolio", portfolioData);
        result.put("websocket_connections", equityWebSocketHandler.getConnectionCount());
        result.put("market_status", marketData);
        result.put("market_open", marketStatus.isOpen());
        
        return result;
    }

    @PostMapping("/portfolio-manager/cycle")
    public ResponseEntity<Map<String, Object>> triggerCycle() {
        // Check market hours first
        if (!marketHoursService.isTradingAllowed()) {
            MarketHoursService.MarketStatus status = marketHoursService.getDetailedMarketStatus();
            return ResponseEntity.badRequest().body(Map.of(
                    "message", "Cannot run trading cycle - market is closed",
                    "status", "market_closed",
                    "market_status", status.status(),
                    "detail", status.detail(),
                    "next_open", status.nextOpenDisplay() != null ? status.nextOpenDisplay() : "Unknown"
            ));
        }
        
        if (tradingCycleScheduler.isRunning()) {
            return ResponseEntity.ok(Map.of(
                    "message", "Trading cycle already running",
                    "status", "running",
                    "cycle", tradingCycleScheduler.getCurrentCycleNumber()
            ));
        }
        
        tradingCycleScheduler.triggerManualCycle();
        
        return ResponseEntity.ok(Map.of(
                "message", "Trading cycle triggered",
                "status", "started",
                "cycle", tradingCycleScheduler.getCurrentCycleNumber() + 1
        ));
    }
    
    @GetMapping("/market-status")
    public Map<String, Object> getMarketStatus() {
        MarketHoursService.MarketStatus status = marketHoursService.getDetailedMarketStatus();
        
        Map<String, Object> result = new HashMap<>();
        result.put("status", status.status());
        result.put("description", status.description());
        result.put("detail", status.detail());
        result.put("is_open", status.isOpen());
        result.put("trading_allowed", status.isTradingAllowed());
        result.put("seconds_until_open", status.secondsUntilOpen());
        result.put("seconds_until_close", status.secondsUntilClose());
        if (status.nextOpen() != null) {
            result.put("next_open", status.nextOpen().toString());
        }
        if (status.nextClose() != null) {
            result.put("next_close", status.nextClose().toString());
        }
        if (status.nextOpenDisplay() != null) {
            result.put("next_open_display", status.nextOpenDisplay());
        }
        result.put("data_source", status.dataSource());
        result.put("polygon_api_available", marketHoursService.isPolygonApiAvailable());
        
        return result;
    }
}

