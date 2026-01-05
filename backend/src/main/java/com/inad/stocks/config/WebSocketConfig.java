package com.inad.stocks.config;

import com.inad.stocks.websocket.EquityWebSocketHandler;
import com.inad.stocks.websocket.EventWebSocketHandler;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

/**
 * WebSocket Configuration for real-time updates
 * 
 * Endpoints:
 * - /ws/equity - Real-time equity streaming (every second)
 * - /ws - General event streaming (signals, trades, risk alerts)
 */
@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final EquityWebSocketHandler equityWebSocketHandler;
    private final EventWebSocketHandler eventWebSocketHandler;

    public WebSocketConfig(EquityWebSocketHandler equityWebSocketHandler,
                          EventWebSocketHandler eventWebSocketHandler) {
        this.equityWebSocketHandler = equityWebSocketHandler;
        this.eventWebSocketHandler = eventWebSocketHandler;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(equityWebSocketHandler, "/ws/equity")
                .setAllowedOrigins("*");
        
        registry.addHandler(eventWebSocketHandler, "/ws")
                .setAllowedOrigins("*");
        
        // Legacy endpoint for backward compatibility
        registry.addHandler(eventWebSocketHandler, "/ws/live")
                .setAllowedOrigins("*");
    }
}

