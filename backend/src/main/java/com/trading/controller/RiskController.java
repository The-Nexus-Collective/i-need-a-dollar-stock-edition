package com.trading.controller;

import com.trading.entity.RiskEvent;
import com.trading.service.RiskService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Risk API endpoints
 */
@RestController
@RequestMapping("/api/risk")
@RequiredArgsConstructor
public class RiskController {

    private final RiskService riskService;

    @GetMapping("/events")
    public List<RiskEvent> getRiskEvents(@RequestParam(defaultValue = "100") int limit) {
        return riskService.getRecentEvents(limit);
    }

    @GetMapping("/events/severity/{severity}")
    public List<RiskEvent> getEventsBySeverity(@PathVariable String severity) {
        return riskService.getEventsBySeverity(severity);
    }

    @GetMapping("/events/unacknowledged")
    public List<RiskEvent> getUnacknowledgedEvents() {
        return riskService.getUnacknowledgedEvents();
    }

    @PostMapping("/events/{id}/acknowledge")
    public ResponseEntity<RiskEvent> acknowledgeEvent(
            @PathVariable UUID id,
            @RequestParam(defaultValue = "system") String acknowledgedBy) {
        return ResponseEntity.ok(riskService.acknowledgeEvent(id, acknowledgedBy));
    }

    @GetMapping("/summary")
    public RiskService.RiskSummary getSummary() {
        return riskService.getSummary();
    }

    @GetMapping("/status")
    public Map<String, Object> getRiskStatus() {
        RiskService.RiskSummary summary = riskService.getSummary();
        
        String status = summary.getCriticalCount() > 0 ? "critical" :
                        summary.getWarningCount() > 0 ? "warning" : "healthy";
        
        return Map.of(
                "status", status,
                "critical_count", summary.getCriticalCount(),
                "warning_count", summary.getWarningCount(),
                "unacknowledged_count", summary.getUnacknowledgedCount()
        );
    }
}

