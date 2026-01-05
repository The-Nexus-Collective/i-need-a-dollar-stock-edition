package com.inad.stocks.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.Set;

/**
 * Service for managing stock market trading hours.
 * 
 * NYSE/NASDAQ Trading Hours (Eastern Time):
 * - Regular Trading: 09:30 - 16:00 ET
 * - Pre-Market: 04:00 - 09:30 ET
 * - After-Hours: 16:00 - 20:00 ET
 * 
 * Market Holidays (US):
 * - New Year's Day, MLK Day, Presidents' Day, Good Friday,
 *   Memorial Day, Independence Day, Labor Day, Thanksgiving, Christmas
 */
@Slf4j
@Service
public class MarketHoursService {
    
    private static final ZoneId ET_ZONE = ZoneId.of("America/New_York");
    private static final LocalTime MARKET_OPEN = LocalTime.of(9, 30);
    private static final LocalTime MARKET_CLOSE = LocalTime.of(16, 0);
    private static final LocalTime PRE_MARKET_OPEN = LocalTime.of(4, 0);
    private static final LocalTime AFTER_HOURS_CLOSE = LocalTime.of(20, 0);
    
    @Value("${stocks.trading-hours.allow-premarket:false}")
    private boolean allowPremarket;
    
    @Value("${stocks.trading-hours.allow-afterhours:false}")
    private boolean allowAfterHours;
    
    // Major US market holidays for 2024-2026 (approximate)
    private static final Set<LocalDate> MARKET_HOLIDAYS = Set.of(
        // 2024
        LocalDate.of(2024, 1, 1),   // New Year's Day
        LocalDate.of(2024, 1, 15),  // MLK Day
        LocalDate.of(2024, 2, 19),  // Presidents' Day
        LocalDate.of(2024, 3, 29),  // Good Friday
        LocalDate.of(2024, 5, 27),  // Memorial Day
        LocalDate.of(2024, 6, 19),  // Juneteenth
        LocalDate.of(2024, 7, 4),   // Independence Day
        LocalDate.of(2024, 9, 2),   // Labor Day
        LocalDate.of(2024, 11, 28), // Thanksgiving
        LocalDate.of(2024, 12, 25), // Christmas
        // 2025
        LocalDate.of(2025, 1, 1),
        LocalDate.of(2025, 1, 20),
        LocalDate.of(2025, 2, 17),
        LocalDate.of(2025, 4, 18),
        LocalDate.of(2025, 5, 26),
        LocalDate.of(2025, 6, 19),
        LocalDate.of(2025, 7, 4),
        LocalDate.of(2025, 9, 1),
        LocalDate.of(2025, 11, 27),
        LocalDate.of(2025, 12, 25),
        // 2026
        LocalDate.of(2026, 1, 1),
        LocalDate.of(2026, 1, 19),
        LocalDate.of(2026, 2, 16),
        LocalDate.of(2026, 4, 3),
        LocalDate.of(2026, 5, 25),
        LocalDate.of(2026, 6, 19),
        LocalDate.of(2026, 7, 3),   // Observed
        LocalDate.of(2026, 9, 7),
        LocalDate.of(2026, 11, 26),
        LocalDate.of(2026, 12, 25)
    );
    
    /**
     * Check if the market is currently open for regular trading.
     */
    public boolean isMarketOpen() {
        ZonedDateTime now = ZonedDateTime.now(ET_ZONE);
        return isMarketOpen(now);
    }
    
    /**
     * Check if the market is open at a specific time.
     */
    public boolean isMarketOpen(ZonedDateTime time) {
        LocalDate date = time.toLocalDate();
        LocalTime localTime = time.toLocalTime();
        
        // Check if it's a weekend
        DayOfWeek day = date.getDayOfWeek();
        if (day == DayOfWeek.SATURDAY || day == DayOfWeek.SUNDAY) {
            return false;
        }
        
        // Check if it's a holiday
        if (MARKET_HOLIDAYS.contains(date)) {
            return false;
        }
        
        // Check if within trading hours
        return !localTime.isBefore(MARKET_OPEN) && localTime.isBefore(MARKET_CLOSE);
    }
    
    /**
     * Check if it's currently pre-market hours.
     */
    public boolean isPreMarket() {
        ZonedDateTime now = ZonedDateTime.now(ET_ZONE);
        LocalDate date = now.toLocalDate();
        LocalTime localTime = now.toLocalTime();
        
        // Check if it's a trading day
        DayOfWeek day = date.getDayOfWeek();
        if (day == DayOfWeek.SATURDAY || day == DayOfWeek.SUNDAY) {
            return false;
        }
        if (MARKET_HOLIDAYS.contains(date)) {
            return false;
        }
        
        return !localTime.isBefore(PRE_MARKET_OPEN) && localTime.isBefore(MARKET_OPEN);
    }
    
    /**
     * Check if it's currently after-hours trading.
     */
    public boolean isAfterHours() {
        ZonedDateTime now = ZonedDateTime.now(ET_ZONE);
        LocalDate date = now.toLocalDate();
        LocalTime localTime = now.toLocalTime();
        
        // Check if it's a trading day
        DayOfWeek day = date.getDayOfWeek();
        if (day == DayOfWeek.SATURDAY || day == DayOfWeek.SUNDAY) {
            return false;
        }
        if (MARKET_HOLIDAYS.contains(date)) {
            return false;
        }
        
        return !localTime.isBefore(MARKET_CLOSE) && localTime.isBefore(AFTER_HOURS_CLOSE);
    }
    
    /**
     * Check if trading is allowed right now based on market hours and configuration.
     */
    public boolean isTradingAllowed() {
        if (isMarketOpen()) {
            return true;
        }
        if (allowPremarket && isPreMarket()) {
            return true;
        }
        if (allowAfterHours && isAfterHours()) {
            return true;
        }
        return false;
    }
    
    /**
     * Get the duration until the market opens.
     */
    public Duration timeUntilOpen() {
        if (isMarketOpen()) {
            return Duration.ZERO;
        }
        
        ZonedDateTime now = ZonedDateTime.now(ET_ZONE);
        ZonedDateTime nextOpen = getNextOpenTime();
        
        return Duration.between(now, nextOpen);
    }
    
    /**
     * Get the duration until the market closes.
     */
    public Duration timeUntilClose() {
        if (!isMarketOpen()) {
            return Duration.ZERO;
        }
        
        ZonedDateTime now = ZonedDateTime.now(ET_ZONE);
        ZonedDateTime todayClose = now.toLocalDate().atTime(MARKET_CLOSE).atZone(ET_ZONE);
        
        return Duration.between(now, todayClose);
    }
    
    /**
     * Get the next market opening time.
     */
    public ZonedDateTime getNextOpenTime() {
        ZonedDateTime now = ZonedDateTime.now(ET_ZONE);
        LocalDate date = now.toLocalDate();
        LocalTime time = now.toLocalTime();
        
        // If market is open, return current day's open time
        if (isMarketOpen()) {
            return date.atTime(MARKET_OPEN).atZone(ET_ZONE);
        }
        
        // If before open today and it's a trading day
        if (time.isBefore(MARKET_OPEN) && isTradingDay(date)) {
            return date.atTime(MARKET_OPEN).atZone(ET_ZONE);
        }
        
        // Find next trading day
        LocalDate nextTradingDay = date.plusDays(1);
        while (!isTradingDay(nextTradingDay)) {
            nextTradingDay = nextTradingDay.plusDays(1);
        }
        
        return nextTradingDay.atTime(MARKET_OPEN).atZone(ET_ZONE);
    }
    
    /**
     * Check if a given date is a trading day.
     */
    public boolean isTradingDay(LocalDate date) {
        DayOfWeek day = date.getDayOfWeek();
        if (day == DayOfWeek.SATURDAY || day == DayOfWeek.SUNDAY) {
            return false;
        }
        return !MARKET_HOLIDAYS.contains(date);
    }
    
    /**
     * Get the current market status as a human-readable string.
     */
    public MarketStatus getMarketStatus() {
        if (isMarketOpen()) {
            Duration untilClose = timeUntilClose();
            return new MarketStatus("OPEN", "Market is open", 
                    formatDuration(untilClose) + " until close", null);
        }
        
        if (isPreMarket()) {
            Duration untilOpen = Duration.between(
                    ZonedDateTime.now(ET_ZONE).toLocalTime().atDate(LocalDate.now()).atZone(ET_ZONE),
                    LocalDate.now().atTime(MARKET_OPEN).atZone(ET_ZONE)
            );
            return new MarketStatus("PRE_MARKET", "Pre-market trading", 
                    formatDuration(untilOpen) + " until regular hours", null);
        }
        
        if (isAfterHours()) {
            return new MarketStatus("AFTER_HOURS", "After-hours trading", 
                    "Regular trading closed", null);
        }
        
        Duration untilOpen = timeUntilOpen();
        ZonedDateTime nextOpen = getNextOpenTime();
        return new MarketStatus("CLOSED", "Market is closed", 
                "Opens " + formatDuration(untilOpen), 
                nextOpen.format(DateTimeFormatter.ofPattern("EEE MMM d, HH:mm z")));
    }
    
    private String formatDuration(Duration duration) {
        long hours = duration.toHours();
        long minutes = duration.toMinutesPart();
        
        if (hours > 24) {
            long days = hours / 24;
            hours = hours % 24;
            return String.format("%dd %dh %dm", days, hours, minutes);
        } else if (hours > 0) {
            return String.format("%dh %dm", hours, minutes);
        } else {
            return String.format("%dm", minutes);
        }
    }
    
    /**
     * Market status information.
     */
    public record MarketStatus(
        String status,
        String description,
        String detail,
        String nextOpenDisplay,
        Long secondsUntilOpen,
        Long secondsUntilClose,
        ZonedDateTime nextOpen,
        ZonedDateTime nextClose,
        boolean tradingAllowed
    ) {
        // Convenience constructor for backward compatibility
        public MarketStatus(String status, String description, String detail, String nextOpenDisplay) {
            this(status, description, detail, nextOpenDisplay, null, null, null, null, "OPEN".equals(status));
        }
        
        public boolean isOpen() {
            return "OPEN".equals(status);
        }
        
        public boolean shouldFlatten() {
            // In stock trading, we typically flatten at market close
            return "AFTER_HOURS".equals(status) || "CLOSED".equals(status);
        }
        
        public String getFlattenReason() {
            if ("CLOSED".equals(status) || "AFTER_HOURS".equals(status)) {
                return "Market closed for regular trading";
            }
            return null;
        }
        
        public Long getSecondsUntilOpen() {
            return secondsUntilOpen;
        }
        
        public Long getSecondsUntilClose() {
            return secondsUntilClose;
        }
        
        public ZonedDateTime getNextOpen() {
            return nextOpen;
        }
        
        public ZonedDateTime getNextClose() {
            return nextClose;
        }
        
        public String getStatusText() {
            return description;
        }
        
        public String getNextEvent() {
            return detail;
        }
        
        public boolean isTradingAllowed() {
            return tradingAllowed;
        }
    }
    
    /**
     * Get detailed market status with calculated time values.
     */
    public MarketStatus getDetailedMarketStatus() {
        ZonedDateTime now = ZonedDateTime.now(ET_ZONE);
        LocalDate date = now.toLocalDate();
        
        boolean isOpen = isMarketOpen();
        boolean isPremarket = isPreMarket();
        boolean isAfterHrs = isAfterHours();
        boolean tradingAllowed = isTradingAllowed();
        
        Long secondsUntilOpen = null;
        Long secondsUntilClose = null;
        ZonedDateTime nextOpenTime = null;
        ZonedDateTime nextCloseTime = null;
        
        if (isOpen) {
            // Calculate time until close
            ZonedDateTime todayClose = date.atTime(MARKET_CLOSE).atZone(ET_ZONE);
            secondsUntilClose = Duration.between(now, todayClose).getSeconds();
            nextCloseTime = todayClose;
            
            return new MarketStatus(
                "OPEN",
                "Market is open",
                formatDuration(Duration.ofSeconds(secondsUntilClose)) + " until close",
                null,
                0L,
                secondsUntilClose,
                null,
                nextCloseTime,
                true
            );
        }
        
        // Calculate time until next open
        nextOpenTime = getNextOpenTime();
        secondsUntilOpen = Duration.between(now, nextOpenTime).getSeconds();
        
        if (isPremarket) {
            return new MarketStatus(
                "PRE_MARKET",
                "Pre-market trading",
                formatDuration(Duration.ofSeconds(secondsUntilOpen)) + " until regular hours",
                nextOpenTime.format(DateTimeFormatter.ofPattern("EEE MMM d, HH:mm z")),
                secondsUntilOpen,
                null,
                nextOpenTime,
                null,
                allowPremarket
            );
        }
        
        if (isAfterHrs) {
            return new MarketStatus(
                "AFTER_HOURS",
                "After-hours trading",
                "Next open: " + formatDuration(Duration.ofSeconds(secondsUntilOpen)),
                nextOpenTime.format(DateTimeFormatter.ofPattern("EEE MMM d, HH:mm z")),
                secondsUntilOpen,
                null,
                nextOpenTime,
                null,
                allowAfterHours
            );
        }
        
        // Market is closed (weekend or holiday or outside hours)
        DayOfWeek day = date.getDayOfWeek();
        String closedReason = "Market is closed";
        if (day == DayOfWeek.SATURDAY || day == DayOfWeek.SUNDAY) {
            closedReason = "Weekend - Market closed";
        } else if (MARKET_HOLIDAYS.contains(date)) {
            closedReason = "Holiday - Market closed";
        }
        
        return new MarketStatus(
            "CLOSED",
            closedReason,
            "Opens " + formatDuration(Duration.ofSeconds(secondsUntilOpen)),
            nextOpenTime.format(DateTimeFormatter.ofPattern("EEE MMM d, HH:mm z")),
            secondsUntilOpen,
            null,
            nextOpenTime,
            null,
            false
        );
    }
}

