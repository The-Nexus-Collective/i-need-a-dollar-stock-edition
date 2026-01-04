package com.trading.controller;

import com.trading.integration.binance.BinanceClient;
import com.trading.integration.binance.BinanceWebSocketClient;
import com.trading.websocket.EquityWebSocketHandler;
import com.trading.websocket.EventWebSocketHandler;
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

    private final BinanceClient binanceClient;
    private final BinanceWebSocketClient binanceWebSocketClient;
    private final EquityWebSocketHandler equityWebSocketHandler;
    private final EventWebSocketHandler eventWebSocketHandler;

    @Value("${trading.mode:paper}")
    private String tradingMode;

    @GetMapping("/system/status")
    public Map<String, Object> getSystemStatus() {
        return Map.of(
                "status", "running",
                "mode", tradingMode,
                "timestamp", Instant.now().toString(),
                "websocket", Map.of(
                        "equity_connections", equityWebSocketHandler.getConnectionCount(),
                        "event_connections", eventWebSocketHandler.getTotalConnectionCount(),
                        "binance_connected", binanceWebSocketClient.isConnected()
                ),
                "version", "1.0.0"
        );
    }

    @GetMapping("/debug/prices")
    public Map<String, Object> getDebugPrices() {
        Map<String, BigDecimal> prices = binanceClient.getAllCachedPrices();
        return Map.of(
                "count", prices.size(),
                "prices", prices,
                "binance_ws_connected", binanceWebSocketClient.isConnected()
        );
    }

    @GetMapping("/debug/price/{symbol}")
    public Map<String, Object> getPrice(@PathVariable String symbol) {
        BigDecimal price = binanceClient.getPrice(symbol);
        return Map.of(
                "symbol", symbol,
                "price", price,
                "timestamp", Instant.now().toString()
        );
    }
}

