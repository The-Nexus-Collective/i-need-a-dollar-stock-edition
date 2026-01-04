package com.trading.websocket;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
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
 * WebSocket handler for general event streaming
 * 
 * Broadcasts trading events to connected clients:
 * - signal: New trading signals
 * - position: Position opened/closed
 * - risk: Risk alerts
 * - system: System status updates
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class EventWebSocketHandler extends TextWebSocketHandler {

    private final Map<String, Set<WebSocketSession>> channelSessions = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper;

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        String channel = getChannel(session);
        channelSessions.computeIfAbsent(channel, k -> ConcurrentHashMap.newKeySet()).add(session);
        log.info("Event WebSocket connected to channel '{}': {}", channel, session.getId());
        
        // Send connection confirmation
        Map<String, Object> message = Map.of(
            "type", "connected",
            "channel", channel,
            "timestamp", Instant.now().toString()
        );
        session.sendMessage(new TextMessage(objectMapper.writeValueAsString(message)));
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        channelSessions.values().forEach(sessions -> sessions.remove(session));
        log.debug("Event WebSocket disconnected: {}", session.getId());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        String payload = message.getPayload();
        if ("ping".equals(payload)) {
            session.sendMessage(new TextMessage("pong"));
        }
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) throws Exception {
        log.warn("WebSocket transport error: {}", exception.getMessage());
        channelSessions.values().forEach(sessions -> sessions.remove(session));
    }

    /**
     * Broadcast event to a specific channel
     */
    public void broadcastToChannel(String channel, Map<String, Object> event) {
        Set<WebSocketSession> sessions = channelSessions.get(channel);
        if (sessions == null || sessions.isEmpty()) {
            return;
        }

        Map<String, Object> message = Map.of(
            "type", "event",
            "event_type", event.getOrDefault("type", "unknown"),
            "data", event,
            "timestamp", Instant.now().toString()
        );

        broadcast(sessions, message);
        
        // Also broadcast to "all" channel
        Set<WebSocketSession> allSessions = channelSessions.get("all");
        if (allSessions != null && !allSessions.isEmpty()) {
            broadcast(allSessions, message);
        }
    }

    /**
     * Broadcast event to all channels
     */
    public void broadcastToAll(Map<String, Object> event) {
        Map<String, Object> message = Map.of(
            "type", "event",
            "event_type", event.getOrDefault("type", "unknown"),
            "data", event,
            "timestamp", Instant.now().toString()
        );

        channelSessions.values().forEach(sessions -> broadcast(sessions, message));
    }

    private void broadcast(Set<WebSocketSession> sessions, Map<String, Object> message) {
        String json;
        try {
            json = objectMapper.writeValueAsString(message);
        } catch (IOException e) {
            log.error("Failed to serialize event: {}", e.getMessage());
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
                log.debug("Failed to send event to session: {}", e.getMessage());
            }
            return true;
        });
    }

    private String getChannel(WebSocketSession session) {
        String query = session.getUri() != null ? session.getUri().getQuery() : null;
        if (query != null && query.contains("channel=")) {
            String[] parts = query.split("channel=");
            if (parts.length > 1) {
                return parts[1].split("&")[0];
            }
        }
        return "all";
    }

    public int getTotalConnectionCount() {
        return channelSessions.values().stream().mapToInt(Set::size).sum();
    }
}

