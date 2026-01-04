package com.trading.controller;

import com.trading.dto.TradeDTO;
import com.trading.service.TradeService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Trade API endpoints
 */
@RestController
@RequestMapping("/api/trades")
@RequiredArgsConstructor
public class TradeController {

    private final TradeService tradeService;

    @GetMapping
    public List<TradeDTO> getTrades(@RequestParam(defaultValue = "100") int limit) {
        return tradeService.getRecentTrades(limit);
    }

    @GetMapping("/today")
    public List<TradeDTO> getTodaysTrades() {
        return tradeService.getTodaysTrades();
    }

    @GetMapping("/symbol/{symbol}")
    public List<TradeDTO> getTradesBySymbol(@PathVariable String symbol) {
        return tradeService.getTradesForSymbol(symbol);
    }

    @GetMapping("/stats")
    public TradeService.TradingStats getStats() {
        return tradeService.getStats();
    }

    @GetMapping("/pnl")
    public Map<String, Object> getPnl() {
        return Map.of(
                "total", tradeService.getTotalPnl(),
                "today", tradeService.getTodaysPnl()
        );
    }
}

