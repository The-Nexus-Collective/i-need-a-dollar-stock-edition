package com.trading.service;

import com.trading.entity.RiskEvent;
import com.trading.repository.RiskEventRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Service for risk management
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RiskService {

    private final RiskEventRepository riskEventRepository;

    /**
     * Get recent risk events
     */
    public List<RiskEvent> getRecentEvents(int limit) {
        return riskEventRepository.findByOrderByTimestampDesc(PageRequest.of(0, limit));
    }

    /**
     * Get events by severity
     */
    public List<RiskEvent> getEventsBySeverity(String severity) {
        return riskEventRepository.findBySeverityOrderByTimestampDesc(severity);
    }

    /**
     * Get unacknowledged events
     */
    public List<RiskEvent> getUnacknowledgedEvents() {
        return riskEventRepository.findByAcknowledgedFalseOrderByTimestampDesc();
    }

    /**
     * Get events since timestamp
     */
    public List<RiskEvent> getEventsSince(Instant since) {
        return riskEventRepository.findEventsSince(since);
    }

    /**
     * Acknowledge a risk event
     */
    @Transactional
    public RiskEvent acknowledgeEvent(UUID eventId, String acknowledgedBy) {
        RiskEvent event = riskEventRepository.findById(eventId)
                .orElseThrow(() -> new RuntimeException("Risk event not found: " + eventId));
        
        event.setAcknowledged(true);
        event.setAcknowledgedBy(acknowledgedBy);
        event.setAcknowledgedAt(Instant.now());
        
        return riskEventRepository.save(event);
    }

    /**
     * Create a new risk event
     */
    @Transactional
    public RiskEvent createRiskEvent(String eventType, String severity, 
                                      BigDecimal triggerValue, BigDecimal thresholdValue,
                                      String actionTaken, Map<String, Object> details) {
        
        log.warn("Risk event: {} [{}] - trigger: {}, threshold: {}", 
                 eventType, severity, triggerValue, thresholdValue);
        
        RiskEvent event = RiskEvent.builder()
                .eventType(eventType)
                .severity(severity)
                .triggerValue(triggerValue)
                .thresholdValue(thresholdValue)
                .actionTaken(actionTaken)
                .details(details)
                .build();
        
        return riskEventRepository.save(event);
    }

    /**
     * Get risk summary
     */
    public RiskSummary getSummary() {
        return RiskSummary.builder()
                .criticalCount(riskEventRepository.countBySeverity("critical"))
                .warningCount(riskEventRepository.countBySeverity("warning"))
                .unacknowledgedCount(riskEventRepository.findByAcknowledgedFalseOrderByTimestampDesc().size())
                .build();
    }
    
    /**
     * Create a margin call warning event (position approaching liquidation).
     */
    @Transactional
    public RiskEvent createMarginWarningEvent(String positionId, String symbol, String direction,
                                               BigDecimal distanceToLiquidation, BigDecimal warningThreshold,
                                               BigDecimal currentPrice, BigDecimal liquidationPrice,
                                               BigDecimal leverage) {
        
        log.warn("MARGIN WARNING: {} {} at {}% distance to liquidation (threshold: {}%)", 
                 symbol, direction, distanceToLiquidation, warningThreshold);
        
        Map<String, Object> details = Map.of(
            "positionId", positionId,
            "symbol", symbol,
            "direction", direction,
            "currentPrice", currentPrice,
            "liquidationPrice", liquidationPrice,
            "leverage", leverage,
            "distanceToLiquidation", distanceToLiquidation
        );
        
        return createRiskEvent(
            "MARGIN_WARNING",
            distanceToLiquidation.compareTo(BigDecimal.valueOf(2)) < 0 ? "critical" : "high",
            distanceToLiquidation,
            warningThreshold,
            "Position monitored - approaching liquidation",
            details
        );
    }
    
    /**
     * Create a margin call execution event (position liquidated).
     */
    @Transactional
    public RiskEvent createMarginCallEvent(String positionId, String symbol, String direction,
                                           BigDecimal entryPrice, BigDecimal exitPrice,
                                           BigDecimal liquidationPrice, BigDecimal lossAmount,
                                           BigDecimal leverage, BigDecimal sizeUsdt) {
        
        log.error("MARGIN CALL EXECUTED: {} {} - Entry: {}, Exit: {}, Loss: {}", 
                  symbol, direction, entryPrice, exitPrice, lossAmount);
        
        Map<String, Object> details = Map.of(
            "positionId", positionId,
            "symbol", symbol,
            "direction", direction,
            "entryPrice", entryPrice,
            "exitPrice", exitPrice,
            "liquidationPrice", liquidationPrice,
            "lossAmount", lossAmount,
            "leverage", leverage,
            "sizeUsdt", sizeUsdt,
            "lossPercent", BigDecimal.valueOf(-100)
        );
        
        return createRiskEvent(
            "MARGIN_CALL",
            "critical",
            exitPrice,
            liquidationPrice,
            "Position force-closed due to margin call - 100% loss",
            details
        );
    }
    
    /**
     * Get recent margin call events
     */
    public List<RiskEvent> getMarginCallEvents(int limit) {
        return riskEventRepository.findByEventTypeOrderByTimestampDesc("MARGIN_CALL", 
                PageRequest.of(0, limit));
    }
    
    /**
     * Count margin call events
     */
    public long countMarginCallEvents() {
        return riskEventRepository.countByEventType("MARGIN_CALL");
    }

    @lombok.Data
    @lombok.Builder
    public static class RiskSummary {
        private long criticalCount;
        private long warningCount;
        private long unacknowledgedCount;
    }
}

