package com.inad.stocks;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Stock Portfolio Manager Application
 * 
 * A portfolio management system for Tech and Defense stocks
 * with AI-powered analysis using Grok.
 */
@SpringBootApplication
@EnableScheduling
public class TradingApplication {

    public static void main(String[] args) {
        SpringApplication.run(TradingApplication.class, args);
    }
}

