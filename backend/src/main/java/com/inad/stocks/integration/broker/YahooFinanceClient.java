package com.inad.stocks.integration.broker;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Stock broker client implementation using Yahoo Finance for price data.
 * 
 * This is a paper trading implementation that:
 * - Fetches real-time stock prices from Yahoo Finance
 * - Simulates order execution with realistic fees
 * - Stores simulated positions in memory (actual persistence in DB via services)
 * 
 * Note: Yahoo Finance API has rate limits. For production, consider Alpha Vantage
 * or a paid data provider.
 */
@Slf4j
@Service
public class YahooFinanceClient implements StockBrokerClient {
    
    private static final String YAHOO_FINANCE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/";
    private static final BigDecimal COMMISSION_PER_TRADE = new BigDecimal("1.00"); // $1 per trade
    private static final Duration TIMEOUT = Duration.ofSeconds(10);
    
    private final WebClient webClient;
    private final ObjectMapper objectMapper;
    
    // Price cache to avoid excessive API calls
    private final Map<String, CachedPrice> priceCache = new ConcurrentHashMap<>();
    private static final long CACHE_TTL_MS = 5000; // 5 seconds cache
    
    @Value("${trading.mode:paper}")
    private String tradingMode;
    
    public YahooFinanceClient(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
        this.webClient = WebClient.builder()
                .baseUrl(YAHOO_FINANCE_URL)
                .defaultHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                .build();
    }
    
    @Override
    public BigDecimal getPrice(String symbol) {
        // Check cache first
        CachedPrice cached = priceCache.get(symbol);
        if (cached != null && !cached.isExpired()) {
            return cached.price;
        }
        
        try {
            String response = webClient.get()
                    .uri(symbol + "?interval=1m&range=1d")
                    .retrieve()
                    .bodyToMono(String.class)
                    .timeout(TIMEOUT)
                    .block();
            
            if (response == null) {
                log.warn("No response from Yahoo Finance for {}", symbol);
                return null;
            }
            
            JsonNode root = objectMapper.readTree(response);
            JsonNode result = root.path("chart").path("result").get(0);
            JsonNode meta = result.path("meta");
            
            BigDecimal price = new BigDecimal(meta.path("regularMarketPrice").asText());
            
            // Cache the price
            priceCache.put(symbol, new CachedPrice(price, System.currentTimeMillis()));
            
            log.debug("Fetched price for {}: ${}", symbol, price);
            return price;
            
        } catch (Exception e) {
            log.error("Failed to fetch price for {}: {}", symbol, e.getMessage());
            // Return cached price if available, even if expired
            if (cached != null) {
                log.warn("Using stale cached price for {}", symbol);
                return cached.price;
            }
            return null;
        }
    }
    
    @Override
    public Map<String, BigDecimal> getPrices(String... symbols) {
        Map<String, BigDecimal> prices = new HashMap<>();
        
        for (String symbol : symbols) {
            BigDecimal price = getPrice(symbol);
            if (price != null) {
                prices.put(symbol, price);
            }
        }
        
        return prices;
    }
    
    @Override
    public TradeResult openPosition(String symbol, String side, BigDecimal amount) {
        log.info("Opening {} position for {} with ${}", side, symbol, amount);
        
        BigDecimal price = getPrice(symbol);
        if (price == null) {
            return TradeResult.failure(symbol, "Could not get current price for " + symbol);
        }
        
        // Calculate quantity - WHOLE SHARES ONLY (no fractional shares)
        BigDecimal quantity = amount.divide(price, 0, RoundingMode.DOWN);
        if (quantity.compareTo(BigDecimal.ONE) < 0) {
            return TradeResult.failure(symbol, 
                    "Amount $" + amount + " too small to buy at least 1 share of " + symbol + " @ $" + price);
        }
        
        // Calculate actual investment amount based on whole shares
        BigDecimal actualAmount = quantity.multiply(price);
        
        // Apply simulated slippage (0.01% - 0.05%)
        BigDecimal slippage = price.multiply(new BigDecimal("0.0003")); // 0.03% average
        BigDecimal executedPrice = "BUY".equalsIgnoreCase(side) 
                ? price.add(slippage) 
                : price.subtract(slippage);
        
        String positionId = UUID.randomUUID().toString().substring(0, 8);
        
        log.info("Executed {} {} {} whole shares @ ${} (market: ${}, requested: ${}, actual: ${})", 
                side, symbol, quantity.intValue(), executedPrice, price, amount, actualAmount);
        
        return TradeResult.success(positionId, symbol, side, executedPrice, quantity, COMMISSION_PER_TRADE);
    }
    
    @Override
    public TradeResult closePosition(String symbol, String side, BigDecimal quantity, BigDecimal entryPrice) {
        // Ensure whole shares only
        BigDecimal wholeQuantity = quantity.setScale(0, RoundingMode.DOWN);
        if (wholeQuantity.compareTo(BigDecimal.ONE) < 0) {
            return TradeResult.failure(symbol, "Cannot close less than 1 whole share");
        }
        
        log.info("Closing position: {} {} {} whole shares (entry: ${})", side, symbol, wholeQuantity.intValue(), entryPrice);
        
        BigDecimal price = getPrice(symbol);
        if (price == null) {
            return TradeResult.failure(symbol, "Could not get current price for " + symbol);
        }
        
        // Apply simulated slippage
        BigDecimal slippage = price.multiply(new BigDecimal("0.0003"));
        BigDecimal executedPrice = "SELL".equalsIgnoreCase(side) 
                ? price.subtract(slippage)  // Selling, so price is slightly lower
                : price.add(slippage);      // Buying (to cover short), so price is slightly higher
        
        // Calculate PnL based on direction
        BigDecimal pnl;
        if ("SELL".equalsIgnoreCase(side)) {
            // Closing a long: profit if price went up
            pnl = executedPrice.subtract(entryPrice).multiply(wholeQuantity);
        } else {
            // Closing a short (buying to cover): profit if price went down
            pnl = entryPrice.subtract(executedPrice).multiply(wholeQuantity);
        }
        
        log.info("Closed {} position: {} whole shares @ ${}, PnL: ${}", 
                symbol, wholeQuantity.intValue(), executedPrice, pnl);
        
        return TradeResult.success(null, symbol, side, executedPrice, wholeQuantity, COMMISSION_PER_TRADE);
    }
    
    @Override
    public boolean isConnected() {
        try {
            BigDecimal price = getPrice("AAPL");
            return price != null;
        } catch (Exception e) {
            log.warn("Connection check failed: {}", e.getMessage());
            return false;
        }
    }
    
    @Override
    public Map<String, BigDecimal> getAllCachedPrices() {
        Map<String, BigDecimal> result = new HashMap<>();
        for (Map.Entry<String, CachedPrice> entry : priceCache.entrySet()) {
            if (!entry.getValue().isExpired()) {
                result.put(entry.getKey(), entry.getValue().price());
            }
        }
        return result;
    }
    
    /**
     * Simple price cache entry.
     */
    private record CachedPrice(BigDecimal price, long timestamp) {
        boolean isExpired() {
            return System.currentTimeMillis() - timestamp > CACHE_TTL_MS;
        }
    }
}

