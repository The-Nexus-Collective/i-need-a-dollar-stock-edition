package com.trading.websocket;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.time.Instant;
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
@RequiredArgsConstructor
public class EquityWebSocketHandler extends TextWebSocketHandler {

    private final Set<WebSocketSession> sessions = ConcurrentHashMap.newKeySet();
    private final ObjectMapper objectMapper;
    
    private String currentPhase = "idle";
    private Long nextCycleAt = null;
    private int cycleNumber = 0;

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        sessions.add(session);
        log.info("Equity WebSocket connected: {}", session.getId());
        
        // Send connection confirmation - check if session is still open first
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
            
            // Send current phase
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
     * This keeps connections alive and prevents load balancer idle timeouts.
     * Note: This is in addition to the 1-second equity broadcasts as a fallback.
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

    private com.trading.service.PositionService positionService;
    private com.trading.service.MarginMonitorService marginMonitorService;

    @org.springframework.beans.factory.annotation.Autowired
    public void setPositionService(com.trading.service.PositionService positionService) {
        this.positionService = positionService;
    }
    
    @org.springframework.beans.factory.annotation.Autowired
    public void setMarginMonitorService(com.trading.service.MarginMonitorService marginMonitorService) {
        this.marginMonitorService = marginMonitorService;
    }

    /**
     * Broadcast equity data to all connected clients and check margin positions.
     * Runs every second for real-time monitoring.
     */
    @Scheduled(fixedRate = 1000)
    public void broadcastEquity() {
        // Always check margins, even if no WebSocket clients
        checkMarginPositions();
        
        if (sessions.isEmpty()) {
            return;
        }
        
        try {
            com.trading.dto.EquityData equityData = positionService.calculateEquityData();
            
            Map<String, Object> message = Map.of(
                "type", "equity_update",
                "data", equityData
            );
            
            broadcast(message);
        } catch (Exception e) {
            log.debug("Failed to broadcast equity: {}", e.getMessage());
        }
    }
    
    /**
     * Check all positions for margin violations.
     * If margin calls are executed, broadcast notifications to all clients.
     */
    private void checkMarginPositions() {
        if (marginMonitorService == null) {
            return;
        }
        
        try {
            com.trading.service.MarginMonitorService.MarginCheckResult result = 
                    marginMonitorService.checkAllPositions();
            
            // Broadcast margin call events if any occurred
            if (result.getMarginCallsExecuted() > 0) {
                for (com.trading.service.MarginMonitorService.MarginCallInfo marginCall : result.getMarginCalls()) {
                    broadcastMarginCall(marginCall);
                }
            }
        } catch (Exception e) {
            log.debug("Failed to check margin positions: {}", e.getMessage());
        }
    }
    
    /**
     * Broadcast margin call notification to all connected clients.
     */
    public void broadcastMarginCall(com.trading.service.MarginMonitorService.MarginCallInfo marginCall) {
        Map<String, Object> message = new java.util.HashMap<>();
        message.put("type", "margin_call");
        message.put("symbol", marginCall.getSymbol());
        message.put("direction", marginCall.getDirection());
        message.put("entry_price", marginCall.getEntryPrice());
        message.put("exit_price", marginCall.getExitPrice());
        message.put("liquidation_price", marginCall.getLiquidationPrice());
        message.put("loss_amount", marginCall.getLossAmount());
        message.put("position_id", marginCall.getPositionId());
        message.put("timestamp", marginCall.getExecutedAt().toString());
        message.put("message", "MARGIN CALL: " + marginCall.getSymbol() + " " + marginCall.getDirection() + 
                               " position liquidated with loss of " + marginCall.getLossAmount());
        
        log.warn("Broadcasting margin call: {} {} - Loss: {}", 
                marginCall.getSymbol(), marginCall.getDirection(), marginCall.getLossAmount());
        
        broadcast(message);
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
            "initial_capital", 100000,
            "timestamp", Instant.now().toString()
        );
        broadcast(message);
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

