package com.trading;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Trading Platform Application
 * 
 * A production-grade autonomous trading platform with:
 * - AI-powered sentiment analysis via Grok
 * - Real-time price data from Binance
 * - WebSocket support for live updates
 * - DB-first architecture with Liquibase migrations
 */
@SpringBootApplication
@EnableScheduling
public class TradingApplication {

    public static void main(String[] args) {
        SpringApplication.run(TradingApplication.class, args);
    }
}

