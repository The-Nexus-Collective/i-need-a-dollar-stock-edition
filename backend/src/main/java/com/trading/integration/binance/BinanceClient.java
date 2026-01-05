package com.trading.integration.binance;

import com.trading.service.FeeService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import jakarta.annotation.PostConstruct;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Binance API client for price data and paper trading
 */
@Slf4j
@Service
public class BinanceClient {

    @Value("${binance.futures-base-url:https://fapi.binance.com}")
    private String futuresBaseUrl;

    @Value("${binance.api-key:}")
    private String apiKey;

    @Value("${trading.mode:paper}")
    private String tradingMode;

    @Autowired
    private FeeService feeService;

    private WebClient webClient;
    private final Map<String, BigDecimal> priceCache = new ConcurrentHashMap<>();
    
    // Slippage for realistic simulation (applied to fill price)
    private static final BigDecimal SLIPPAGE_BASE = new BigDecimal("0.0001"); // 0.01%

    @PostConstruct
    public void init() {
        this.webClient = WebClient.builder()
                .baseUrl(futuresBaseUrl)
                .defaultHeader("X-MBX-APIKEY", apiKey)
                .build();
        log.info("Binance client initialized with mode: {}", tradingMode);
    }

    /**
     * Get current price for a symbol
     */
    public BigDecimal getPrice(String symbol) {
        // Check cache first
        BigDecimal cached = priceCache.get(symbol);
        if (cached != null) {
            return cached;
        }

        try {
            PriceResponse response = webClient.get()
                    .uri("/fapi/v1/ticker/price?symbol={symbol}", symbol)
                    .retrieve()
                    .bodyToMono(PriceResponse.class)
                    .timeout(Duration.ofSeconds(5))
                    .block();
            
            if (response != null && response.price != null) {
                BigDecimal price = new BigDecimal(response.price);
                priceCache.put(symbol, price);
                return price;
            }
        } catch (Exception e) {
            log.warn("Failed to get price for {}: {}", symbol, e.getMessage());
        }
        
        return cached != null ? cached : BigDecimal.ZERO;
    }

    /**
     * Get prices for multiple symbols
     */
    public Map<String, BigDecimal> getPrices(String... symbols) {
        Map<String, BigDecimal> prices = new ConcurrentHashMap<>();
        for (String symbol : symbols) {
            BigDecimal price = getPrice(symbol);
            if (price.compareTo(BigDecimal.ZERO) > 0) {
                prices.put(symbol, price);
            }
        }
        return prices;
    }

    /**
     * Update price cache (called by WebSocket handler)
     */
    public void updatePriceCache(String symbol, BigDecimal price) {
        priceCache.put(symbol, price);
    }

    /**
     * Get all cached prices
     */
    public Map<String, BigDecimal> getAllCachedPrices() {
        return new ConcurrentHashMap<>(priceCache);
    }

    /**
     * Simulate opening a position (paper trading)
     */
    public TradeResult openPosition(String symbol, String side, BigDecimal sizeUsdt, int leverage) {
        BigDecimal price = getPrice(symbol);
        if (price.compareTo(BigDecimal.ZERO) == 0) {
            return TradeResult.builder()
                    .success(false)
                    .error("Failed to get price for " + symbol)
                    .build();
        }

        // Apply slippage to fill price (simulates market impact)
        BigDecimal slippageMultiplier = BigDecimal.ONE.add(
                "BUY".equalsIgnoreCase(side) ? SLIPPAGE_BASE : SLIPPAGE_BASE.negate()
        );
        BigDecimal fillPrice = price.multiply(slippageMultiplier);

        // Calculate trading costs using FeeService (respects VIP tier)
        // Note: Slippage is already reflected in the fillPrice, so we don't add it as separate cost
        // The slippage cost is: |fillPrice - price| * quantity, which equals sizeUsdt * SLIPPAGE_BASE
        // We track this for reporting purposes but it's NOT an additional deduction
        BigDecimal fee = feeService.calculateTakerFee(sizeUsdt);
        BigDecimal slippage = BigDecimal.ZERO; // Already baked into fillPrice - do not double-count
        BigDecimal spread = sizeUsdt.multiply(new BigDecimal("0.0001")); // 0.01% spread estimate

        // Calculate quantity
        BigDecimal quantity = sizeUsdt.divide(fillPrice, 8, RoundingMode.HALF_UP);

        log.info("Paper trade opened: {} {} {} @ {} (fee: {}, spread: {}, slippage in price: {}%)", 
                 side, quantity, symbol, fillPrice, fee, spread, SLIPPAGE_BASE.multiply(new BigDecimal("100")));

        return TradeResult.builder()
                .success(true)
                .symbol(symbol)
                .side(side)
                .price(fillPrice)
                .quantity(quantity)
                .fee(fee)
                .spread(spread)
                .slippage(slippage)
                .leverage(leverage)
                .build();
    }

    /**
     * Simulate closing a position (paper trading)
     */
    public TradeResult closePosition(String symbol, String side, BigDecimal quantity, BigDecimal entryPrice) {
        BigDecimal price = getPrice(symbol);
        if (price.compareTo(BigDecimal.ZERO) == 0) {
            return TradeResult.builder()
                    .success(false)
                    .error("Failed to get price for " + symbol)
                    .build();
        }

        // Apply slippage (opposite direction for close)
        BigDecimal slippageMultiplier = BigDecimal.ONE.add(
                "BUY".equalsIgnoreCase(side) ? SLIPPAGE_BASE.negate() : SLIPPAGE_BASE
        );
        BigDecimal fillPrice = price.multiply(slippageMultiplier);

        // Calculate PnL
        BigDecimal pnl;
        if ("LONG".equalsIgnoreCase(side) || "BUY".equalsIgnoreCase(side)) {
            pnl = fillPrice.subtract(entryPrice).multiply(quantity);
        } else {
            pnl = entryPrice.subtract(fillPrice).multiply(quantity);
        }

        // Calculate and deduct fee using FeeService (respects VIP tier)
        BigDecimal sizeUsdt = fillPrice.multiply(quantity);
        BigDecimal fee = feeService.calculateTakerFee(sizeUsdt);

        log.info("Paper trade closed: {} {} @ {} (PnL: {}, fee: {})", 
                 quantity, symbol, fillPrice, pnl, fee);

        // Return raw PnL without fee subtraction - accounting handles fees separately
        return TradeResult.builder()
                .success(true)
                .symbol(symbol)
                .side(side)
                .price(fillPrice)
                .quantity(quantity)
                .fee(fee)
                .pnl(pnl)
                .build();
    }

    /**
     * Get funding rate for a symbol
     */
    public BigDecimal getFundingRate(String symbol) {
        try {
            FundingRateResponse response = webClient.get()
                    .uri("/fapi/v1/fundingRate?symbol={symbol}&limit=1", symbol)
                    .retrieve()
                    .bodyToFlux(FundingRateResponse.class)
                    .next()
                    .timeout(Duration.ofSeconds(5))
                    .block();
            
            if (response != null && response.fundingRate != null) {
                return new BigDecimal(response.fundingRate);
            }
        } catch (Exception e) {
            log.debug("Failed to get funding rate for {}: {}", symbol, e.getMessage());
        }
        return BigDecimal.ZERO;
    }

    // Response DTOs
    private static class PriceResponse {
        public String symbol;
        public String price;
    }

    private static class FundingRateResponse {
        public String symbol;
        public String fundingRate;
        public Long fundingTime;
    }

    @lombok.Data
    @lombok.Builder
    public static class TradeResult {
        private boolean success;
        private String symbol;
        private String side;
        private BigDecimal price;
        private BigDecimal quantity;
        private BigDecimal fee;
        private BigDecimal spread;
        private BigDecimal slippage;
        private BigDecimal pnl;
        private int leverage;
        private String error;
    }
}

