package com.trading.service;

import com.trading.entity.Position;
import com.trading.integration.binance.BinanceClient;
import lombok.Builder;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * Service to check the status of Pre-Mortem predictions for open positions.
 * 
 * Analyzes whether Grok's pre-trade concerns are materializing:
 * - OK: Nothing indicates the Pre-Mortem is coming true
 * - WARNING: Some signs that the Pre-Mortem might be coming true
 * - TRIGGERED: Pre-Mortem appears to be happening
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PreMortemCheckerService {

    private final BinanceClient binanceClient;

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);
    private static final BigDecimal WARNING_LOSS_THRESHOLD = new BigDecimal("-5");
    private static final BigDecimal TRIGGERED_LOSS_THRESHOLD = new BigDecimal("-10");
    private static final BigDecimal DRAWDOWN_WARNING_THRESHOLD = new BigDecimal("0.05");
    private static final int STALE_HOURS_THRESHOLD = 12;
    private static final BigDecimal STALE_PNL_THRESHOLD = new BigDecimal("3");

    public enum PreMortemStatus {
        OK,       // Nothing indicates Pre-Mortem is coming true
        WARNING,  // Some signs the Pre-Mortem might be happening
        TRIGGERED // Pre-Mortem appears to be happening
    }

    @Data
    @Builder
    public static class PreMortemCheckResult {
        private PreMortemStatus status;
        private List<String> signals;
        private BigDecimal currentPnlPercent;
        private int holdTimeHours;
        private BigDecimal highSinceEntry;
        private BigDecimal lowSinceEntry;
        private BigDecimal currentPrice;
    }

    /**
     * Check if a position's Pre-Mortem is materializing.
     */
    public PreMortemCheckResult checkPreMortem(Position position) {
        BigDecimal currentPrice = binanceClient.getPrice(position.getSymbol());
        if (currentPrice == null || currentPrice.compareTo(BigDecimal.ZERO) == 0) {
            log.warn("Could not get price for {}", position.getSymbol());
            return PreMortemCheckResult.builder()
                    .status(PreMortemStatus.OK)
                    .signals(List.of("Could not fetch current price"))
                    .currentPnlPercent(BigDecimal.ZERO)
                    .holdTimeHours(0)
                    .build();
        }

        BigDecimal pnlPercent = position.calculatePnlPercent(currentPrice);
        Duration holdTime = Duration.between(position.getEntryTime(), Instant.now());
        int holdHours = (int) holdTime.toHours();

        PreMortemStatus status = PreMortemStatus.OK;
        List<String> signals = new ArrayList<>();

        // Check 1: Significant loss
        if (pnlPercent.compareTo(TRIGGERED_LOSS_THRESHOLD) < 0) {
            status = PreMortemStatus.TRIGGERED;
            signals.add(String.format("PnL bei %.1f%% - erheblicher Verlust", pnlPercent));
        } else if (pnlPercent.compareTo(WARNING_LOSS_THRESHOLD) < 0) {
            status = PreMortemStatus.WARNING;
            signals.add(String.format("PnL bei %.1f%% - Position läuft gegen dich", pnlPercent));
        }

        // Check 2: Stale position (long hold time without movement)
        if (holdHours > STALE_HOURS_THRESHOLD && 
            pnlPercent.abs().compareTo(STALE_PNL_THRESHOLD) < 0) {
            if (status == PreMortemStatus.OK) {
                status = PreMortemStatus.WARNING;
            }
            signals.add(String.format("%d+ Stunden ohne signifikante Bewegung", STALE_HOURS_THRESHOLD));
        }

        // Check 3: Expected hold time exceeded
        if (position.getExpectedHoldHoursMax() != null && 
            holdHours > position.getExpectedHoldHoursMax()) {
            if (status == PreMortemStatus.OK) {
                status = PreMortemStatus.WARNING;
            }
            signals.add(String.format("Erwartete Haltezeit (%dh) überschritten", 
                    position.getExpectedHoldHoursMax()));
        }

        // Check 4: Drawdown from high (for LONG) / Rally from low (for SHORT)
        BigDecimal entryPrice = position.getEntryPrice();
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            // For LONG: Check if price went up and then fell back
            BigDecimal maxPossibleHigh = currentPrice.max(entryPrice);
            BigDecimal drawdownFromEntry = entryPrice.subtract(currentPrice)
                    .divide(entryPrice, 4, RoundingMode.HALF_UP);
            
            if (drawdownFromEntry.compareTo(DRAWDOWN_WARNING_THRESHOLD) > 0) {
                if (status == PreMortemStatus.OK) {
                    status = PreMortemStatus.WARNING;
                }
                signals.add(String.format("Preis fiel %.1f%% seit Entry", 
                        drawdownFromEntry.multiply(HUNDRED)));
            }
        } else {
            // For SHORT: Check if price went down and then rose back
            BigDecimal rallyFromEntry = currentPrice.subtract(entryPrice)
                    .divide(entryPrice, 4, RoundingMode.HALF_UP);
            
            if (rallyFromEntry.compareTo(DRAWDOWN_WARNING_THRESHOLD) > 0) {
                if (status == PreMortemStatus.OK) {
                    status = PreMortemStatus.WARNING;
                }
                signals.add(String.format("Preis stieg %.1f%% seit Entry", 
                        rallyFromEntry.multiply(HUNDRED)));
            }
        }

        // Check 5: Maximum acceptable loss exceeded
        if (position.getMaxAcceptableLossPercent() != null && 
            pnlPercent.compareTo(position.getMaxAcceptableLossPercent().negate()) < 0) {
            status = PreMortemStatus.TRIGGERED;
            signals.add(String.format("Max. akzeptabler Verlust (%.1f%%) überschritten", 
                    position.getMaxAcceptableLossPercent()));
        }

        // Check 6: Target PnL was reached but then lost
        if (position.getTargetPnlPercent() != null && 
            pnlPercent.compareTo(position.getTargetPnlPercent()) < 0) {
            // This would require tracking high PnL - simplified check
            if (pnlPercent.compareTo(BigDecimal.ZERO) < 0 && 
                position.getTargetPnlPercent().compareTo(BigDecimal.TEN) <= 0) {
                signals.add("Gewinn-Ziel nicht erreicht, jetzt im Minus");
            }
        }

        return PreMortemCheckResult.builder()
                .status(status)
                .signals(signals)
                .currentPnlPercent(pnlPercent)
                .holdTimeHours(holdHours)
                .currentPrice(currentPrice)
                .build();
    }

    /**
     * Get a summary message for the Pre-Mortem status.
     */
    public String getStatusSummary(PreMortemCheckResult result) {
        return switch (result.getStatus()) {
            case OK -> "Pre-Mortem nicht eingetreten";
            case WARNING -> "Pre-Mortem könnte eintreten";
            case TRIGGERED -> "Pre-Mortem scheint einzutreten!";
        };
    }

    /**
     * Get emoji for status display.
     */
    public String getStatusEmoji(PreMortemStatus status) {
        return switch (status) {
            case OK -> "✅";
            case WARNING -> "⚠️";
            case TRIGGERED -> "🚨";
        };
    }
}

