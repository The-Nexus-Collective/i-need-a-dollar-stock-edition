package com.inad.stocks.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.inad.stocks.dto.ClosedPositionInfo;
import com.inad.stocks.dto.ExtendedPositionInfo;
import com.inad.stocks.dto.LogbookEntryDTO;
import com.inad.stocks.dto.OpenedPositionInfo;
import com.inad.stocks.dto.ReducedPositionInfo;
import com.inad.stocks.entity.LogbookEntry;
import com.inad.stocks.service.LogbookService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Logbook API endpoints - provides trading cycle history
 */
@Slf4j
@RestController
@RequestMapping("/api/logbook")
@RequiredArgsConstructor
public class LogbookController {

    private final LogbookService logbookService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @GetMapping
    public List<LogbookEntryDTO> getLogbookEntries(@RequestParam(defaultValue = "50") int limit) {
        return logbookService.getLatest(limit).stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    @GetMapping("/{id}")
    public ResponseEntity<LogbookEntryDTO> getLogbookEntry(@PathVariable String id) {
        return logbookService.getById(id)
                .map(entry -> ResponseEntity.ok(convertToDTO(entry)))
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/cycle/{cycleNumber}")
    public ResponseEntity<LogbookEntryDTO> getLogbookEntryByCycle(@PathVariable int cycleNumber) {
        return logbookService.getByCycle(cycleNumber)
                .map(entry -> ResponseEntity.ok(convertToDTO(entry)))
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/search")
    public List<LogbookEntryDTO> searchLogbook(@RequestParam String query) {
        return logbookService.search(query).stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    @GetMapping("/stats")
    public Map<String, Object> getLogbookStats() {
        return logbookService.getStatistics();
    }
    
    private LogbookEntryDTO convertToDTO(LogbookEntry entry) {
        List<LogbookEntryDTO.PositionAction> opened = parsePositionsOpened(entry.getPositionsOpened());
        List<LogbookEntryDTO.PositionAction> closed = parsePositionsClosed(entry.getPositionsClosed());
        List<String> kept = parseStringList(entry.getPositionsKept());
        List<LogbookEntryDTO.ScaledPositionAction> extended = parsePositionsExtended(entry.getPositionsExtended());
        List<LogbookEntryDTO.ScaledPositionAction> reduced = parsePositionsReduced(entry.getPositionsReduced());
        
        return LogbookEntryDTO.builder()
                .id(entry.getId())
                .timestamp(entry.getTimestamp())
                .cycleNumber(entry.getCycleNumber())
                .analysisText(entry.getAnalysisText())
                .marketSummary(entry.getMarketSummary())
                .positionsClosed(closed)
                .positionsOpened(opened)
                .positionsKept(kept)
                .positionsExtended(extended)
                .positionsReduced(reduced)
                .stocksAnalyzed(entry.getStocksAnalyzed())
                .stocksSkipped(entry.getStocksSkipped())
                .tokensUsed(entry.getTokensUsed())
                .totalEquity(entry.getTotalEquity())
                .unrealizedPnl(entry.getUnrealizedPnl())
                .openPositions(entry.getOpenPositions())
                .deploymentPercent(entry.getDeploymentPercent())
                .rawPrompt(entry.getRawPrompt())
                .rawResponse(entry.getRawResponse())
                .build();
    }
    
    @SuppressWarnings("unchecked")
    private List<String> parseStringList(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            return objectMapper.readValue(json, new TypeReference<List<String>>() {});
        } catch (Exception e) {
            return Collections.emptyList();
        }
    }
    
    @SuppressWarnings("unchecked")
    private List<LogbookEntryDTO.PositionAction> parsePositionsOpened(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            List<OpenedPositionInfo> infos = objectMapper.readValue(json, new TypeReference<List<OpenedPositionInfo>>() {});
            return infos.stream()
                    .map(info -> LogbookEntryDTO.PositionAction.builder()
                            .symbol(info.getSymbol())
                            .direction(info.getDirection())
                            .price(info.getEntryPrice())
                            .size(info.getSizeUsd())
                            .conviction(info.getConviction())
                            .reason(info.getReason())
                            .build())
                    .collect(Collectors.toList());
        } catch (Exception e) {
            log.debug("Failed to parse positions opened: {}", e.getMessage());
            return Collections.emptyList();
        }
    }
    
    @SuppressWarnings("unchecked")
    private List<LogbookEntryDTO.PositionAction> parsePositionsClosed(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            List<ClosedPositionInfo> infos = objectMapper.readValue(json, new TypeReference<List<ClosedPositionInfo>>() {});
            return infos.stream()
                    .map(info -> LogbookEntryDTO.PositionAction.builder()
                            .symbol(info.getSymbol())
                            .direction(info.getDirection())
                            .price(info.getExitPrice())
                            .pnl(info.getPnl())
                            .pnlPercent(info.getPnlPercent())
                            .reason(info.getReason())
                            .build())
                    .collect(Collectors.toList());
        } catch (Exception e) {
            log.debug("Failed to parse positions closed: {}", e.getMessage());
            return Collections.emptyList();
        }
    }
    
    @SuppressWarnings("unchecked")
    private List<LogbookEntryDTO.ScaledPositionAction> parsePositionsExtended(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            List<ExtendedPositionInfo> infos = objectMapper.readValue(json, new TypeReference<List<ExtendedPositionInfo>>() {});
            return infos.stream()
                    .map(info -> LogbookEntryDTO.ScaledPositionAction.builder()
                            .symbol(info.getSymbol())
                            .scalePercent(info.getScalePercent())
                            .price(info.getPrice())
                            .size(info.getAddedSize())
                            .reason(info.getReason())
                            .build())
                    .collect(Collectors.toList());
        } catch (Exception e) {
            log.debug("Failed to parse positions extended: {}", e.getMessage());
            return Collections.emptyList();
        }
    }
    
    @SuppressWarnings("unchecked")
    private List<LogbookEntryDTO.ScaledPositionAction> parsePositionsReduced(String json) {
        if (json == null || json.isEmpty()) return Collections.emptyList();
        try {
            List<ReducedPositionInfo> infos = objectMapper.readValue(json, new TypeReference<List<ReducedPositionInfo>>() {});
            return infos.stream()
                    .map(info -> LogbookEntryDTO.ScaledPositionAction.builder()
                            .symbol(info.getSymbol())
                            .scalePercent(info.getScalePercent())
                            .price(info.getPrice())
                            .size(info.getReducedSize())
                            .pnl(info.getPartialPnl())
                            .reason(info.getReason())
                            .build())
                    .collect(Collectors.toList());
        } catch (Exception e) {
            log.debug("Failed to parse positions reduced: {}", e.getMessage());
            return Collections.emptyList();
        }
    }
}
