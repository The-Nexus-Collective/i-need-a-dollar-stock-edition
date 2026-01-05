package com.inad.stocks.integration.grok.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Complete result from Grok analysis for stock trading.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnalysisResult {
    
    // Human-readable analysis (stored in logbook)
    private String analysisText;
    private String marketSummary;
    
    // Structured decisions
    @Builder.Default
    private List<PositionDecision> positionDecisions = Collections.emptyList();
    
    @Builder.Default
    private List<NewOpportunity> newOpportunities = Collections.emptyList();
    
    // Metadata
    private int stocksAnalyzed;
    private int stocksSkipped;
    
    @Builder.Default
    private Instant timestamp = Instant.now();
    
    private int tokensUsed;
    
    // Debug: raw AI prompt and response
    private String rawPrompt;
    private String rawResponse;
    
    // Error if analysis failed
    private String error;
    
    /**
     * Check if analysis was successful
     */
    public boolean isSuccessful() {
        return error == null || error.isEmpty();
    }
    
    /**
     * Get symbols that Grok recommends closing
     */
    public List<String> getPositionsToClose() {
        return positionDecisions.stream()
                .filter(d -> d.getAction() == PositionDecision.Action.CLOSE)
                .map(PositionDecision::getSymbol)
                .collect(Collectors.toList());
    }
    
    /**
     * Get symbols that Grok recommends keeping
     */
    public List<String> getPositionsToKeep() {
        return positionDecisions.stream()
                .filter(d -> d.getAction() == PositionDecision.Action.KEEP)
                .map(PositionDecision::getSymbol)
                .collect(Collectors.toList());
    }
    
    /**
     * Get positions that Grok recommends extending
     */
    public List<PositionDecision> getPositionsToExtend() {
        return positionDecisions.stream()
                .filter(d -> d.getAction() == PositionDecision.Action.EXTEND)
                .collect(Collectors.toList());
    }
    
    /**
     * Get positions that Grok recommends reducing
     */
    public List<PositionDecision> getPositionsToReduce() {
        return positionDecisions.stream()
                .filter(d -> d.getAction() == PositionDecision.Action.REDUCE)
                .collect(Collectors.toList());
    }
    
    /**
     * Get opportunities sorted by conviction (highest first)
     */
    public List<NewOpportunity> getOpportunitiesByConviction() {
        return newOpportunities.stream()
                .sorted((a, b) -> Integer.compare(b.getConviction(), a.getConviction()))
                .collect(Collectors.toList());
    }
    
    /**
     * Create an empty/error result
     */
    public static AnalysisResult error(String errorMessage, String rawPrompt, String rawResponse) {
        return AnalysisResult.builder()
                .analysisText("⚠️ Analysis could not be completed: " + errorMessage)
                .marketSummary("Analysis unavailable")
                .positionDecisions(Collections.emptyList())
                .newOpportunities(Collections.emptyList())
                .stocksAnalyzed(0)
                .stocksSkipped(0)
                .error(errorMessage)
                .rawPrompt(rawPrompt)
                .rawResponse(rawResponse)
                .build();
    }
}

