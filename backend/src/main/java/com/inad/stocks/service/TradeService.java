package com.inad.stocks.service;

import com.inad.stocks.dto.TradeDTO;
import com.inad.stocks.entity.Trade;
import com.inad.stocks.repository.TradeRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Service for trade management
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TradeService {

    private final TradeRepository tradeRepository;

    /**
     * Get recent trades
     */
    public List<TradeDTO> getRecentTrades(int limit) {
        return tradeRepository.findByOrderByExitTimeDesc(PageRequest.of(0, limit))
                .stream()
                .map(this::toDTO)
                .collect(Collectors.toList());
    }

    /**
     * Get trades since timestamp
     */
    public List<TradeDTO> getTradesSince(Instant since) {
        return tradeRepository.findTradesSince(since)
                .stream()
                .map(this::toDTO)
                .collect(Collectors.toList());
    }

    /**
     * Get daily trades
     */
    public List<TradeDTO> getTodaysTrades() {
        Instant startOfDay = Instant.now().truncatedTo(ChronoUnit.DAYS);
        return getTradesSince(startOfDay);
    }

    /**
     * Get trades for a symbol
     */
    public List<TradeDTO> getTradesForSymbol(String symbol) {
        return tradeRepository.findBySymbolOrderByExitTimeDesc(symbol)
                .stream()
                .map(this::toDTO)
                .collect(Collectors.toList());
    }

    /**
     * Calculate total PnL
     */
    public BigDecimal getTotalPnl() {
        return tradeRepository.calculateTotalPnl();
    }

    /**
     * Calculate today's PnL
     */
    public BigDecimal getTodaysPnl() {
        Instant startOfDay = Instant.now().truncatedTo(ChronoUnit.DAYS);
        return tradeRepository.calculatePnlSince(startOfDay);
    }

    /**
     * Get trading statistics
     */
    public TradingStats getStats() {
        int winning = tradeRepository.countWinningTrades();
        int losing = tradeRepository.countLosingTrades();
        int total = winning + losing;
        BigDecimal winRate = total > 0 
                ? BigDecimal.valueOf(winning).divide(BigDecimal.valueOf(total), 4, java.math.RoundingMode.HALF_UP).multiply(BigDecimal.valueOf(100))
                : BigDecimal.ZERO;
        
        return TradingStats.builder()
                .totalTrades(total)
                .winningTrades(winning)
                .losingTrades(losing)
                .winRate(winRate)
                .totalPnl(tradeRepository.calculateTotalPnl())
                .avgPnlPercent(tradeRepository.calculateAveragePnlPercent())
                .build();
    }

    private TradeDTO toDTO(Trade t) {
        return TradeDTO.builder()
                .id(t.getId())
                .positionId(t.getPositionId())
                .symbol(t.getSymbol())
                .direction(t.getDirection())
                .entryPrice(t.getEntryPrice())
                .exitPrice(t.getExitPrice())
                .quantity(t.getQuantity())
                .sizeUsd(t.getSizeUsd())
                .leverage(t.getLeverage())
                .pnlUsd(t.getPnlUsd())
                .pnlPercent(t.getPnlPercent())
                .entryTime(t.getEntryTime())
                .exitTime(t.getExitTime())
                .durationSeconds(t.getDurationSeconds())
                .exitReason(t.getExitReason())
                .conviction(t.getConviction())
                .reasoning(t.getReasoning())
                .totalFees(t.getTotalFees())
                .build();
    }

    @lombok.Data
    @lombok.Builder
    public static class TradingStats {
        private int totalTrades;
        private int winningTrades;
        private int losingTrades;
        private BigDecimal winRate;
        private BigDecimal totalPnl;
        private BigDecimal avgPnlPercent;
    }
}

