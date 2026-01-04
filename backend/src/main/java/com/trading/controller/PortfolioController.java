package com.trading.controller;

import com.trading.dto.PortfolioResponse;
import com.trading.dto.PositionDTO;
import com.trading.scheduler.TradingCycleScheduler;
import com.trading.service.PortfolioService;
import com.trading.service.PositionService;
import com.trading.websocket.EquityWebSocketHandler;
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

    @Value("${trading.capital.starting:100000}")
    private BigDecimal startingCapital;

    @Value("${trading.position.max-positions:50}")
    private int maxPositions;

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
                .map(PositionDTO::getSizeUsdt)
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
        statistics.put("max_positions", maxPositions);
        statistics.put("available_slots", maxPositions - portfolio.getOpenPositions());
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
        
        Map<String, Object> result = new HashMap<>();
        result.put("status", "running");
        result.put("mode", "paper");
        result.put("portfolio", portfolioData);
        result.put("websocket_connections", equityWebSocketHandler.getConnectionCount());
        
        return result;
    }

    @PostMapping("/portfolio-manager/cycle")
    public ResponseEntity<Map<String, Object>> triggerCycle() {
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
}

