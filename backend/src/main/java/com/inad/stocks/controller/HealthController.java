package com.inad.stocks.controller;

import com.inad.stocks.dto.HealthResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;

/**
 * Health check controller
 */
@RestController
public class HealthController {

    @Value("${trading.mode:paper}")
    private String tradingMode;

    @GetMapping("/health")
    public HealthResponse healthCheck() {
        return HealthResponse.builder()
                .status("healthy")
                .timestamp(Instant.now().toString())
                .version("1.0.0")
                .mode(tradingMode)
                .build();
    }
}

