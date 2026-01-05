package com.inad.stocks.controller;

import com.inad.stocks.integration.broker.StockBrokerClient;
import com.inad.stocks.service.MarketHoursService;
import com.inad.stocks.websocket.EquityWebSocketHandler;
import com.inad.stocks.websocket.EventWebSocketHandler;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Map;

/**
 * System status and debug endpoints
 */
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class SystemController {

    private final StockBrokerClient stockBrokerClient;
    private final EquityWebSocketHandler equityWebSocketHandler;
    private final EventWebSocketHandler eventWebSocketHandler;
    private final MarketHoursService marketHoursService;

    @Value("${trading.mode:paper}")
    private String tradingMode;

    @GetMapping("/system/status")
    public Map<String, Object> getSystemStatus() {
        MarketHoursService.MarketStatus marketStatus = marketHoursService.getMarketStatus();
        
        return Map.of(
                "status", "running",
                "mode", tradingMode,
                "timestamp", Instant.now().toString(),
                "websocket_connections", equityWebSocketHandler.getConnectionCount(),
                "event_streams", Map.of(
                        "connections", eventWebSocketHandler.getTotalConnectionCount()
                ),
                "market_status", Map.of(
                        "is_open", marketStatus.isOpen(),
                        "next_open", marketStatus.getNextOpen() != null ? marketStatus.getNextOpen().toString() : null,
                        "next_close", marketStatus.getNextClose() != null ? marketStatus.getNextClose().toString() : null
                ),
                "broker_connected", stockBrokerClient.isConnected(),
                "version", "1.0.0-stocks"
        );
    }

    @GetMapping("/debug/prices")
    public Map<String, Object> getDebugPrices() {
        Map<String, BigDecimal> prices = stockBrokerClient.getAllCachedPrices();
        return Map.of(
                "count", prices.size(),
                "prices", prices,
                "broker_connected", stockBrokerClient.isConnected()
        );
    }

    @GetMapping("/debug/price/{symbol}")
    public Map<String, Object> getPrice(@PathVariable String symbol) {
        BigDecimal price = stockBrokerClient.getPrice(symbol);
        return Map.of(
                "symbol", symbol,
                "price", price != null ? price : "N/A",
                "timestamp", Instant.now().toString()
        );
    }
    
    @GetMapping("/stocks/market-status")
    public Map<String, Object> getMarketStatus() {
        MarketHoursService.MarketStatus status = marketHoursService.getMarketStatus();
        
        return Map.of(
                "is_open", status.isOpen(),
                "current_time", Instant.now().toString(),
                "timezone", "America/New_York",
                "time_to_open_seconds", status.getSecondsUntilOpen(),
                "time_to_close_seconds", status.getSecondsUntilClose(),
                "should_flatten", status.shouldFlatten(),
                "flatten_reason", status.getFlattenReason() != null ? status.getFlattenReason() : "",
                "status_text", status.getStatusText(),
                "next_event", status.getNextEvent()
        );
    }
}
