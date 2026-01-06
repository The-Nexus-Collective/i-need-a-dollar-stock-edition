package com.inad.stocks.service;

import com.inad.stocks.dto.PortfolioResponse;
import com.inad.stocks.dto.PositionDTO;
import com.inad.stocks.entity.TraderState;
import com.inad.stocks.repository.TraderStateRepository;
import com.inad.stocks.repository.TradeRepository;
import com.inad.stocks.repository.PositionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

/**
 * Service for portfolio management.
 * Now uses AccountingService as the single source of truth for capital.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PortfolioService {

    private final TraderStateRepository traderStateRepository;
    private final PositionRepository positionRepository;
    private final TradeRepository tradeRepository;
    private final PositionService positionService;
    private final AccountingService accountingService;
    private final LogbookService logbookService;

    @Value("${trading.capital.starting:0}")
    private BigDecimal defaultStartingCapital;

    /**
     * Get current portfolio status.
     * Uses AccountingService for authoritative capital values.
     */
    public PortfolioResponse getPortfolio() {
        TraderState state = traderStateRepository.getOrCreateMain();
        List<PositionDTO> openPositions = positionService.getOpenPositions();
        
        // Get values from accounting ledger (single source of truth)
        BigDecimal cash = accountingService.getCashBalance();
        BigDecimal positionsEntryCost = accountingService.getPositionsValue();
        BigDecimal realizedPnl = accountingService.getRealizedPnl();
        BigDecimal tradingCosts = accountingService.getTradingCosts();
        BigDecimal startingCapital = accountingService.getStartingCapitalFromLedger();
        
        // If ledger is not initialized, use state values as fallback
        if (startingCapital.compareTo(BigDecimal.ZERO) == 0) {
            startingCapital = state.getStartingCapital();
            cash = state.getCurrentCapital();
        }
        
        // Calculate unrealized PnL from live position prices
        BigDecimal unrealizedPnl = openPositions.stream()
                .map(p -> p.getUnrealizedPnl() != null ? p.getUnrealizedPnl() : BigDecimal.ZERO)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        
        // Total equity = cash + positions current market value
        // = cash + positions entry cost + unrealized PnL
        BigDecimal positionsCurrentValue = positionsEntryCost.add(unrealizedPnl);
        BigDecimal totalEquity = cash.add(positionsCurrentValue);
        
        // Total PnL = realized + unrealized
        BigDecimal totalPnl = realizedPnl.add(unrealizedPnl);
        
        BigDecimal pnlPercent = BigDecimal.ZERO;
        if (startingCapital.compareTo(BigDecimal.ZERO) > 0) {
            pnlPercent = totalPnl
                    .divide(startingCapital, 4, RoundingMode.HALF_UP)
                    .multiply(BigDecimal.valueOf(100));
        }
        
        // Get detailed cost breakdown from ledger metadata
        BigDecimal totalFees = accountingService.getTotalFees();
        BigDecimal totalSpread = accountingService.getTotalSpread();
        BigDecimal totalSlippage = accountingService.getTotalSlippage();
        
        return PortfolioResponse.builder()
                .totalEquity(totalEquity)
                .initialCapital(startingCapital)
                .cash(cash)
                .positionsValue(positionsEntryCost)
                .unrealizedPnl(unrealizedPnl)
                .realizedPnl(realizedPnl)
                .totalPnl(totalPnl)
                .pnlPercent(pnlPercent)
                .openPositions(openPositions.size())
                .totalTrades(state.getTotalTrades())
                .winningTrades(state.getWinningTrades())
                .losingTrades(state.getLosingTrades())
                .winRate(state.getWinRate())
                .totalVolume(BigDecimal.ZERO)
                .totalFees(totalFees)
                .totalSpread(totalSpread)
                .totalSlippage(totalSlippage)
                .totalTradingCosts(tradingCosts)
                .var95(null)
                .maxDrawdown(state.getMaxDrawdown())
                .build();
    }

    /**
     * Reset paper trading - closes all positions and resets capital.
     * Records reset in accounting ledger for audit trail.
     */
    @Transactional
    public void resetPaperTrades(BigDecimal startingCapital) {
        log.info("Resetting paper trades with starting capital: {}", startingCapital);
        
        // Close all open positions (delete from DB)
        List<PositionDTO> openPositions = positionService.getOpenPositions();
        for (PositionDTO pos : openPositions) {
            positionRepository.deleteById(pos.getId());
        }
        
        // Record reset in accounting ledger (clears old entries and establishes new capital)
        accountingService.recordReset(startingCapital);
        
        // Clear logbook entries
        logbookService.reset();
        
        // Reset trader state statistics
        TraderState state = traderStateRepository.getOrCreateMain();
        state.setCurrentCapital(startingCapital); // Keep for backwards compatibility
        state.setStartingCapital(startingCapital);
        state.setPeakCapital(startingCapital);
        state.setTotalPnl(BigDecimal.ZERO);
        state.setTotalTrades(0);
        state.setWinningTrades(0);
        state.setLosingTrades(0);
        state.setMaxDrawdown(BigDecimal.ZERO);
        state.setTotalFeesPaid(BigDecimal.ZERO);
        state.setTotalSlippageCost(BigDecimal.ZERO);
        state.setTotalCycles(0);
        
        traderStateRepository.save(state);
        
        log.info("Paper trades reset complete. Accounting ledger initialized with {} USDT", startingCapital);
    }

    /**
     * Get win rate from closed trades
     */
    public BigDecimal getWinRate() {
        int total = tradeRepository.countWinningTrades() + tradeRepository.countLosingTrades();
        if (total == 0) return BigDecimal.ZERO;
        
        return BigDecimal.valueOf(tradeRepository.countWinningTrades())
                .divide(BigDecimal.valueOf(total), 4, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));
    }
}

