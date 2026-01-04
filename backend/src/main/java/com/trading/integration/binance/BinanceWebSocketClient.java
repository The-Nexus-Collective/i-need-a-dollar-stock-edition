package com.trading.integration.binance;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.math.BigDecimal;
import java.net.URI;
import java.util.*;
import java.util.concurrent.*;

/**
 * Binance WebSocket client for real-time price streaming
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class BinanceWebSocketClient {

    @Value("${binance.websocket-url:wss://fstream.binance.com/ws}")
    private String wsUrl;

    private final BinanceClient binanceClient;
    private final ObjectMapper objectMapper;

    private WebSocketClient wsClient;
    private final ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor();
    private volatile boolean connected = false;

    // Default trading pairs to subscribe to
    private static final List<String> DEFAULT_SYMBOLS = List.of(
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"
    );

    @PostConstruct
    public void init() {
        connect();
        
        // Reconnect scheduler
        scheduler.scheduleAtFixedRate(() -> {
            if (!connected) {
                log.info("Attempting Binance WebSocket reconnection...");
                connect();
            }
        }, 30, 30, TimeUnit.SECONDS);
    }

    @PreDestroy
    public void shutdown() {
        scheduler.shutdown();
        if (wsClient != null) {
            wsClient.close();
        }
    }

    public void connect() {
        try {
            // Build combined stream URL
            String streamPath = DEFAULT_SYMBOLS.stream()
                    .map(s -> s.toLowerCase() + "@markPrice")
                    .reduce((a, b) -> a + "/" + b)
                    .orElse("");
            
            URI uri = URI.create(wsUrl + "/" + streamPath);
            
            wsClient = new WebSocketClient(uri) {
                @Override
                public void onOpen(ServerHandshake handshake) {
                    connected = true;
                    log.info("Binance WebSocket connected");
                }

                @Override
                public void onMessage(String message) {
                    handleMessage(message);
                }

                @Override
                public void onClose(int code, String reason, boolean remote) {
                    connected = false;
                    log.warn("Binance WebSocket closed: {} ({})", reason, code);
                }

                @Override
                public void onError(Exception ex) {
                    log.error("Binance WebSocket error: {}", ex.getMessage());
                }
            };
            
            wsClient.connect();
            
        } catch (Exception e) {
            log.error("Failed to connect to Binance WebSocket: {}", e.getMessage());
        }
    }

    private void handleMessage(String message) {
        try {
            JsonNode node = objectMapper.readTree(message);
            
            // Handle mark price update
            if (node.has("s") && node.has("p")) {
                String symbol = node.get("s").asText();
                BigDecimal price = new BigDecimal(node.get("p").asText());
                binanceClient.updatePriceCache(symbol, price);
            }
            // Handle stream wrapper
            else if (node.has("data")) {
                JsonNode data = node.get("data");
                if (data.has("s") && data.has("p")) {
                    String symbol = data.get("s").asText();
                    BigDecimal price = new BigDecimal(data.get("p").asText());
                    binanceClient.updatePriceCache(symbol, price);
                }
            }
        } catch (Exception e) {
            log.debug("Failed to parse Binance message: {}", e.getMessage());
        }
    }

    public boolean isConnected() {
        return connected;
    }

    /**
     * Subscribe to additional symbols
     */
    public void subscribe(String... symbols) {
        if (!connected || wsClient == null) {
            log.warn("Cannot subscribe: WebSocket not connected");
            return;
        }

        try {
            List<String> streams = Arrays.stream(symbols)
                    .map(s -> s.toLowerCase() + "@markPrice")
                    .toList();
            
            Map<String, Object> request = Map.of(
                    "method", "SUBSCRIBE",
                    "params", streams,
                    "id", System.currentTimeMillis()
            );
            
            wsClient.send(objectMapper.writeValueAsString(request));
            log.info("Subscribed to symbols: {}", Arrays.toString(symbols));
            
        } catch (Exception e) {
            log.error("Failed to subscribe: {}", e.getMessage());
        }
    }
}

