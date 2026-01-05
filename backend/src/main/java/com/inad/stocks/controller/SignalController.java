package com.inad.stocks.controller;

import com.inad.stocks.entity.Signal;
import com.inad.stocks.service.SignalService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

/**
 * Signal API endpoints
 */
@RestController
@RequestMapping("/api/signals")
@RequiredArgsConstructor
public class SignalController {

    private final SignalService signalService;

    @GetMapping
    public List<Signal> getSignals(@RequestParam(defaultValue = "100") int limit) {
        return signalService.getRecentSignals(limit);
    }

    @GetMapping("/today")
    public List<Signal> getTodaysSignals() {
        return signalService.getSignalsSince(Instant.now().truncatedTo(ChronoUnit.DAYS));
    }

    @GetMapping("/coin/{coin}")
    public List<Signal> getSignalsByCoin(@PathVariable String coin) {
        return signalService.getSignalsForCoin(coin);
    }

    @GetMapping("/executed")
    public List<Signal> getExecutedSignals() {
        return signalService.getExecutedSignals();
    }
}

