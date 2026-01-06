package com.inad.stocks.websocket;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.inad.stocks.dto.PositionDTO;
import com.inad.stocks.integration.broker.StockBrokerClient;
import com.inad.stocks.service.AccountingService;
import com.inad.stocks.service.PositionService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * WebSocket handler for real-time equity streaming
 * 
 * Broadcasts equity updates every second to all connected clients.
 * Messages include:
 * - equity_update: Current portfolio equity data
 * - phase: Trading cycle phase (idle, fetching, analyzing, trading)
 * - paper_trades_reset: Notification when trades are reset
 */
@Slf4j
@Component
public class EquityWebSocketHandler extends TextWebSocketHandler {

    private final Set<WebSocketSession> sessions = ConcurrentHashMap.newKeySet();
    private final ObjectMapper objectMapper;
    
    @Autowired(required = false)
    private PositionService positionService;
    
    @Autowired(required = false)
    private AccountingService accountingService;
    
    @Autowired(required = false)
    private StockBrokerClient stockBrokerClient;
    
    private String currentPhase = "idle";
    private Long nextCycleAt = null;
    private int cycleNumber = 0;
    
    public EquityWebSocketHandler(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        sessions.add(session);
        log.info("Equity WebSocket connected: {}", session.getId());
        
        if (!session.isOpen()) {
            sessions.remove(session);
            log.debug("Session {} closed before messages could be sent", session.getId());
            return;
        }
        
        try {
            Map<String, Object> message = Map.of(
                "type", "connected",
                "timestamp", Instant.now().toString()
            );
            session.sendMessage(new TextMessage(objectMapper.writeValueAsString(message)));
            
            sendPhaseUpdate(session);
        } catch (IOException e) {
            log.debug("Failed to send initial messages to session {}: {}", session.getId(), e.getMessage());
            sessions.remove(session);
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        sessions.remove(session);
        log.debug("Equity WebSocket disconnected: {}", session.getId());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        String payload = message.getPayload();
        if ("ping".equals(payload) && session.isOpen()) {
            try {
                session.sendMessage(new TextMessage("pong"));
            } catch (IOException e) {
                log.debug("Failed to send pong to session {}: {}", session.getId(), e.getMessage());
                sessions.remove(session);
            }
        }
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) throws Exception {
        log.warn("WebSocket transport error: {}", exception.getMessage());
        sessions.remove(session);
    }

    /**
     * Send heartbeat to all connected clients every 20 seconds.
     */
    @Scheduled(fixedRate = 20000)
    public void sendHeartbeat() {
        if (sessions.isEmpty()) {
            return;
        }
        
        Map<String, Object> heartbeat = Map.of(
            "type", "heartbeat",
            "timestamp", Instant.now().toString()
        );
        broadcast(heartbeat);
    }
    
    /**
     * Broadcast equity data to all connected clients every 5 seconds.
     * This provides the data for the equity chart on the frontend.
     */
    @Scheduled(fixedRate = 5000)
    public void broadcastEquityUpdate() {
        if (sessions.isEmpty() || positionService == null || accountingService == null) {
            return;
        }
        
        try {
            // Get current positions and calculate equity with live prices
            List<PositionDTO> positions = positionService.getOpenPositions();
            BigDecimal cash = accountingService.getCashBalance();
            
            BigDecimal positionsValue = BigDecimal.ZERO;
            BigDecimal unrealizedPnl = BigDecimal.ZERO;
            
            for (PositionDTO pos : positions) {
                // Get current price for accurate valuation
                BigDecimal currentPrice = pos.getEntryPrice(); // Default to entry
                if (stockBrokerClient != null) {
                    try {
                        currentPrice = stockBrokerClient.getPrice(pos.getSymbol());
                    } catch (Exception e) {
                        // Use entry price if live price unavailable
                    }
                }
                
                // Calculate current value
                BigDecimal currentValue = currentPrice.multiply(pos.getQuantity());
                positionsValue = positionsValue.add(currentValue);
                
                // Calculate unrealized PnL
                BigDecimal entryValue = pos.getEntryPrice().multiply(pos.getQuantity());
                BigDecimal pnl = "LONG".equalsIgnoreCase(pos.getDirection()) 
                        ? currentValue.subtract(entryValue)
                        : entryValue.subtract(currentValue);
                unrealizedPnl = unrealizedPnl.add(pnl);
            }
            
            BigDecimal totalEquity = cash.add(positionsValue);
            
            Map<String, Object> equityData = new HashMap<>();
            equityData.put("timestamp", Instant.now().getEpochSecond());
            equityData.put("total_equity", totalEquity);
            equityData.put("unrealized_pnl", unrealizedPnl);
            equityData.put("cash", cash);
            equityData.put("positions_value", positionsValue);
            equityData.put("open_positions", positions.size());
            
            Map<String, Object> message = new HashMap<>();
            message.put("type", "equity");
            message.putAll(equityData);
            
            broadcast(message);
        } catch (Exception e) {
            log.debug("Failed to broadcast equity update: {}", e.getMessage());
        }
    }

    /**
     * Broadcast phase update to all clients
     */
    public void broadcastPhase(String phase, Long nextCycleAtTimestamp, int cycle) {
        this.currentPhase = phase;
        this.nextCycleAt = nextCycleAtTimestamp;
        this.cycleNumber = cycle;
        
        log.info("Broadcasting phase: {}", phase);
        
        Map<String, Object> message = new java.util.HashMap<>();
        message.put("type", "phase");
        message.put("phase", phase);
        message.put("timestamp", Instant.now().getEpochSecond());
        
        if (nextCycleAtTimestamp != null) {
            message.put("next_cycle_at", nextCycleAtTimestamp);
        }
        message.put("cycle_number", cycle);
        
        broadcast(message);
    }

    /**
     * Broadcast reset notification
     */
    public void broadcastReset() {
        Map<String, Object> message = Map.of(
            "type", "paper_trades_reset",
            "message", "All paper trades have been reset",
            "initial_capital", 0,
            "timestamp", Instant.now().toString()
        );
        broadcast(message);
    }

    /**
     * Broadcast equity data to all connected clients.
     */
    public void broadcastEquityData(Object equityData) {
        if (sessions.isEmpty()) {
            return;
        }
        
        try {
            Map<String, Object> message = Map.of(
                "type", "equity_update",
                "data", equityData
            );
            
            broadcast(message);
        } catch (Exception e) {
            log.debug("Failed to broadcast equity: {}", e.getMessage());
        }
    }

    private void sendPhaseUpdate(WebSocketSession session) {
        if (!session.isOpen()) {
            return;
        }
        
        try {
            Map<String, Object> message = new java.util.HashMap<>();
            message.put("type", "phase");
            message.put("phase", currentPhase);
            message.put("timestamp", Instant.now().getEpochSecond());
            if (nextCycleAt != null) {
                message.put("next_cycle_at", nextCycleAt);
            }
            message.put("cycle_number", cycleNumber);
            
            session.sendMessage(new TextMessage(objectMapper.writeValueAsString(message)));
        } catch (IOException e) {
            log.debug("Failed to send phase update to session {}: {}", session.getId(), e.getMessage());
            sessions.remove(session);
        }
    }

    private void broadcast(Map<String, Object> message) {
        String json;
        try {
            json = objectMapper.writeValueAsString(message);
        } catch (IOException e) {
            log.error("Failed to serialize message: {}", e.getMessage());
            return;
        }

        TextMessage textMessage = new TextMessage(json);
        sessions.removeIf(session -> {
            try {
                if (session.isOpen()) {
                    session.sendMessage(textMessage);
                    return false;
                }
            } catch (IOException e) {
                log.debug("Failed to send message to session: {}", e.getMessage());
            }
            return true;
        });
    }

    public int getConnectionCount() {
        return sessions.size();
    }
    
    /**
     * Broadcast a raw JSON message to all connected clients.
     */
    public void broadcastMessage(String jsonMessage) {
        if (sessions.isEmpty()) {
            return;
        }
        
        TextMessage textMessage = new TextMessage(jsonMessage);
        sessions.removeIf(session -> {
            try {
                if (session.isOpen()) {
                    session.sendMessage(textMessage);
                    return false;
                }
            } catch (IOException e) {
                log.debug("Failed to send message to session: {}", e.getMessage());
            }
            return true;
        });
    }
}

