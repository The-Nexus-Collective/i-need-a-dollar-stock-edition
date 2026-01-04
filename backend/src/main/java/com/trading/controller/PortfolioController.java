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
        
        // Return format expected by frontend: portfolio.statistics and portfolio.positions
        Map<String, Object> statistics = Map.ofEntries(
                Map.entry("starting_capital", portfolio.getInitialCapital()),
                Map.entry("current_capital", portfolio.getCash()),
                Map.entry("total_equity", portfolio.getTotalEquity()),
                Map.entry("unrealized_pnl", portfolio.getUnrealizedPnl()),
                Map.entry("realized_pnl", portfolio.getRealizedPnl()),
                Map.entry("total_pnl", portfolio.getTotalPnl()),
                Map.entry("open_positions", portfolio.getOpenPositions()),
                Map.entry("max_positions", maxPositions),
                Map.entry("available_slots", maxPositions - portfolio.getOpenPositions()),
                Map.entry("total_trades", portfolio.getTotalTrades()),
                Map.entry("winning_trades", portfolio.getWinningTrades()),
                Map.entry("losing_trades", portfolio.getLosingTrades()),
                Map.entry("win_rate", portfolio.getWinRate()),
                Map.entry("total_fees", portfolio.getTotalFees()),
                Map.entry("total_spread", portfolio.getTotalSpread()),
                Map.entry("total_slippage", portfolio.getTotalSlippage())
        );
        
        // Get actual open positions
        List<PositionDTO> openPositions = positionService.getOpenPositions();
        log.info("getPortfolioManagerStatus: Found {} open positions", openPositions.size());
        
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

