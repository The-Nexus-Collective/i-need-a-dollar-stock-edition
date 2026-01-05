package com.inad.stocks.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.inad.stocks.dto.ClosedPositionInfo;
import com.inad.stocks.dto.ExtendedPositionInfo;
import com.inad.stocks.dto.OpenedPositionInfo;
import com.inad.stocks.dto.ReducedPositionInfo;
import com.inad.stocks.entity.LogbookEntry;
import com.inad.stocks.integration.grok.dto.AnalysisResult;
import com.inad.stocks.repository.LogbookRepository;
import com.inad.stocks.websocket.EquityWebSocketHandler;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;

/**
 * Service for managing trading logbook entries.
 * Stores Grok's analysis text and cycle details for frontend display.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class LogbookService {
    
    private final LogbookRepository logbookRepository;
    private final EquityWebSocketHandler equityWebSocketHandler;
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    /**
     * Log a complete trading cycle.
     */
    @Transactional
    public LogbookEntry log(
            AnalysisResult analysis,
            List<ClosedPositionInfo> closed,
            List<OpenedPositionInfo> opened,
            List<String> kept,
            List<ExtendedPositionInfo> extended,
            List<ReducedPositionInfo> reduced,
            BigDecimal totalEquity,
            BigDecimal unrealizedPnl,
            int openPositionsCount,
            BigDecimal deploymentPercent
    ) {
        int cycleNumber = logbookRepository.getMaxCycleNumber() + 1;
        
        LogbookEntry entry = LogbookEntry.builder()
                .id("LOG_" + UUID.randomUUID().toString().replace("-", "").substring(0, 8).toUpperCase())
                .timestamp(Instant.now())
                .cycleNumber(cycleNumber)
                .analysisText(analysis.getAnalysisText())
                .marketSummary(analysis.getMarketSummary())
                .positionsClosed(toJson(closed))
                .positionsOpened(toJson(opened))
                .positionsKept(toJson(kept))
                .positionsExtended(toJson(extended))
                .positionsReduced(toJson(reduced))
                .stocksAnalyzed(analysis.getStocksAnalyzed())
                .stocksSkipped(analysis.getStocksSkipped())
                .tokensUsed(analysis.getTokensUsed())
                .totalEquity(totalEquity)
                .unrealizedPnl(unrealizedPnl)
                .openPositions(openPositionsCount)
                .deploymentPercent(deploymentPercent)
                .rawPrompt(analysis.getRawPrompt())
                .rawResponse(analysis.getRawResponse())
                .build();
        
        entry = logbookRepository.save(entry);
        
        log.info("📝 Logbook entry #{}: {}", cycleNumber, analysis.getMarketSummary());
        
        // Broadcast to WebSocket clients
        broadcastLogbookEntry(entry);
        
        return entry;
    }
    
    /**
     * Get latest logbook entries.
     */
    public List<LogbookEntry> getLatest(int limit) {
        return logbookRepository.findAll(
                PageRequest.of(0, limit, Sort.by(Sort.Direction.DESC, "timestamp"))
        ).getContent();
    }
    
    /**
     * Get all entries (up to 1000).
     */
    public List<LogbookEntry> getAll() {
        return logbookRepository.findAllByOrderByTimestampDesc();
    }
    
    /**
     * Get entry by ID.
     */
    public Optional<LogbookEntry> getById(String id) {
        return logbookRepository.findById(id);
    }
    
    /**
     * Get entry by cycle number.
     */
    public Optional<LogbookEntry> getByCycle(int cycleNumber) {
        return logbookRepository.findByCycleNumber(cycleNumber);
    }
    
    /**
     * Search entries by analysis text.
     */
    public List<LogbookEntry> search(String query) {
        return logbookRepository.searchByAnalysisText(query);
    }
    
    /**
     * Get statistics about the logbook.
     */
    public Map<String, Object> getStatistics() {
        long totalEntries = logbookRepository.count();
        int maxCycle = logbookRepository.getMaxCycleNumber();
        long totalTokens = logbookRepository.sumTokensUsed();
        
        return Map.of(
                "total_entries", totalEntries,
                "total_cycles", maxCycle,
                "total_tokens_used", totalTokens
        );
    }
    
    /**
     * Reset logbook (for paper trading reset).
     */
    @Transactional
    public void reset() {
        long count = logbookRepository.count();
        logbookRepository.deleteAll();
        log.warn("Logbook reset: cleared {} entries", count);
    }
    
    /**
     * Convert object to JSON string.
     */
    private String toJson(Object obj) {
        if (obj == null) return "[]";
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            log.warn("Failed to serialize to JSON: {}", e.getMessage());
            return "[]";
        }
    }
    
    /**
     * Broadcast logbook entry to WebSocket clients.
     */
    private void broadcastLogbookEntry(LogbookEntry entry) {
        try {
            Map<String, Object> message = new HashMap<>();
            message.put("type", "logbook_entry");
            message.put("data", Map.of(
                    "id", entry.getId(),
                    "timestamp", entry.getTimestamp().toString(),
                    "cycle_number", entry.getCycleNumber(),
                    "market_summary", entry.getMarketSummary() != null ? entry.getMarketSummary() : "",
                    "stocks_analyzed", entry.getStocksAnalyzed(),
                    "open_positions", entry.getOpenPositions(),
                    "total_equity", entry.getTotalEquity(),
                    "unrealized_pnl", entry.getUnrealizedPnl()
            ));
            equityWebSocketHandler.broadcastMessage(objectMapper.writeValueAsString(message));
        } catch (Exception e) {
            log.debug("Failed to broadcast logbook entry: {}", e.getMessage());
        }
    }
}

