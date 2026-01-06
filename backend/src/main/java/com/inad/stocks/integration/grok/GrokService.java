package com.inad.stocks.integration.grok;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.inad.stocks.integration.grok.dto.AnalysisResult;
import com.inad.stocks.integration.grok.dto.NewOpportunity;
import com.inad.stocks.integration.grok.dto.PositionDecision;
import com.inad.stocks.service.MarketHoursService;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.*;

/**
 * Grok AI Service for Stock Portfolio Management.
 * 
 * Uses Grok's real-time capabilities to:
 * 1. Analyze Tech and Defense stocks from our universe
 * 2. Search X/news for sentiment on individual stocks
 * 3. Evaluate open positions (KEEP, CLOSE, EXTEND, REDUCE)
 * 4. Find new opportunities (LONG/SHORT with conviction)
 * 
 * Key differences from crypto:
 * - No leverage (cash account)
 * - Market hours awareness (NYSE/NASDAQ)
 * - Sector-focused (Tech & Defense)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class GrokService {

    private static final int TIMEOUT_SECONDS = 120;
    private static final int MAX_TOKENS = 8000;
    private static final int MAX_RETRY_ATTEMPTS = 3;
    private static final int RETRY_DELAY_MS = 3000;

    @Value("${xai.api-key:}")
    private String apiKey;

    @Value("${xai.base-url:https://api.x.ai/v1}")
    private String baseUrl;

    @Value("${xai.model:grok-4-1-fast-reasoning}")
    private String model;

    private final ObjectMapper objectMapper;
    private WebClient webClient;
    
    @Autowired(required = false)
    private MarketHoursService marketHoursService;

    @PostConstruct
    public void init() {
        this.webClient = WebClient.builder()
                .baseUrl(baseUrl)
                .defaultHeader("Authorization", "Bearer " + apiKey)
                .defaultHeader("Content-Type", "application/json")
                .build();

        if (apiKey != null && !apiKey.isEmpty()) {
            log.info("GrokService initialized with API key ({} chars), model: {}", apiKey.length(), model);
        } else {
            log.warn("GrokService initialized WITHOUT API key - trading cycles will fail!");
        }
    }

    /**
     * Run comprehensive portfolio analysis with automatic retry on empty results.
     * Grok decides how many positions to open based on market conditions - no artificial limits.
     */
    public AnalysisResult analyze(String positionsContext, 
                                   String deploymentInfo, BigDecimal availableCapital) {
        return analyzeWithRetry(positionsContext, deploymentInfo, availableCapital, 1);
    }

    private AnalysisResult analyzeWithRetry(String positionsContext,
                                            String deploymentInfo, BigDecimal availableCapital, int attempt) {
        
        String prompt = buildPrompt(positionsContext, deploymentInfo);
        String systemPrompt = getSystemPrompt();
        String fullPrompt = "[SYSTEM]\n" + systemPrompt + "\n\n[USER]\n" + prompt;

        if (apiKey == null || apiKey.isEmpty()) {
            log.warn("Grok API key not configured, returning empty analysis");
            return AnalysisResult.error("API key not configured", fullPrompt, "");
        }

        try {
            log.info("Sending request to Grok API (model: {}, attempt {}/{})...", model, attempt, MAX_RETRY_ATTEMPTS);

            Map<String, Object> request = new LinkedHashMap<>();
            request.put("model", model);
            request.put("messages", List.of(
                    Map.of("role", "system", "content", systemPrompt),
                    Map.of("role", "user", "content", prompt)
            ));
            request.put("temperature", 0.3);
            request.put("max_tokens", MAX_TOKENS);

            String response = webClient.post()
                    .uri("/chat/completions")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(String.class)
                    .timeout(Duration.ofSeconds(TIMEOUT_SECONDS))
                    .block();

            log.info("Grok API response received ({} chars)", response != null ? response.length() : 0);

            AnalysisResult result = parseResponse(response, fullPrompt);
            log.info("Parsed {} position decisions, {} new opportunities from Grok",
                    result.getPositionDecisions().size(),
                    result.getNewOpportunities().size());

            if (isEmptyAnalysis(result) && attempt < MAX_RETRY_ATTEMPTS) {
                String responsePreview = result.getRawResponse() != null 
                    ? result.getRawResponse().substring(0, Math.min(300, result.getRawResponse().length()))
                    : "null";
                log.warn("Grok returned empty analysis (attempt {}/{}). Response preview: {}", 
                         attempt, MAX_RETRY_ATTEMPTS, responsePreview);
                
                try {
                    Thread.sleep(RETRY_DELAY_MS);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                }
                
                return analyzeWithRetry(positionsContext, deploymentInfo, availableCapital, attempt + 1);
            }

            return result;

        } catch (org.springframework.web.reactive.function.client.WebClientResponseException e) {
            log.error("Grok API error - Status: {}, Body: {}", e.getStatusCode(), e.getResponseBodyAsString());
            return AnalysisResult.error(e.getResponseBodyAsString(), fullPrompt, "");
        } catch (Exception e) {
            log.error("Grok analysis failed: {}", e.getMessage(), e);
            return AnalysisResult.error(e.getMessage(), fullPrompt, "");
        }
    }

    private boolean isEmptyAnalysis(AnalysisResult result) {
        return result.getStocksAnalyzed() == 0 
            && result.getNewOpportunities().isEmpty() 
            && result.getPositionDecisions().isEmpty();
    }

    private String getSystemPrompt() {
        return """
            You are an AGGRESSIVE stock portfolio manager targeting 100%+ ANNUAL RETURNS.
            
            CRITICAL: You MUST use your search tools (x_keyword_search, x_semantic_search, web_search) 
            to gather CURRENT data about stock sentiment, earnings, news, and market conditions.
            
            Your internal knowledge may be outdated. Real-time search results are essential.
            
            STRATEGY:
            - Target: 100%+ annual return (aggressive growth)
            - YOU decide position sizes based on conviction - NO FIXED LIMITS
            - High-conviction trades can use up to 100% of available capital
            - Focus on momentum and catalysts for maximum returns
            
            Focus on:
            - Tech stocks: AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, AMD, etc.
            - Defense stocks: LMT, RTX, NOC, GD, BA, LHX, etc.
            
            Always output valid JSON as specified in the prompt.""";
    }

    private String buildPrompt(String positionsContext, String deploymentInfo) {
        String timestamp = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm 'UTC'")
                .withZone(ZoneOffset.UTC)
                .format(Instant.now());
        
        // Get market status
        String marketStatus = "Market hours not available";
        if (marketHoursService != null) {
            MarketHoursService.MarketStatus status = marketHoursService.getMarketStatus();
            marketStatus = status.status() + " - " + status.detail();
        }

        return String.format("""
            You are a professional stock portfolio manager for Tech and Defense sectors.
            
            ═══════════════════════════════════════════════════════════════════
            CURRENT TIME: %s
            MARKET STATUS: %s
            ═══════════════════════════════════════════════════════════════════
            
            ═══════════════════════════════════════════════════════════════════
            TASK 1: STOCK MARKET ANALYSIS
            ═══════════════════════════════════════════════════════════════════
            
            Analyze the following high-liquidity stocks from our universe:
            
            TECH STOCKS: AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, AMD, INTC, CRM,
                         ORCL, ADBE, CSCO, IBM, QCOM, AVGO, TXN, MU, AMAT, LRCX
            
            DEFENSE STOCKS: LMT, RTX, NOC, GD, BA, LHX, HII, TDG, LDOS
            
            IMPORTANT RULES:
            1. Base your analysis on X posts, news headlines, and market sentiment from the LAST 30 MINUTES
            2. Use your real-time search functions for current data
            3. Consider earnings reports, analyst upgrades/downgrades, and sector news
            4. LONG positions only (no short selling in paper cash account)
            5. Skip stocks where data is too thin - quality over quantity
            
            ═══════════════════════════════════════════════════════════════════
            TASK 2: PORTFOLIO EVALUATION
            ═══════════════════════════════════════════════════════════════════
            
            %s
            
            %s
            
            ═══════════════════════════════════════════════════════════════════
            PATIENCE RULES - STOCKS MOVE SLOWER THAN CRYPTO
            ═══════════════════════════════════════════════════════════════════
            
            MINIMUM HOLD TIME RULES:
            - Hold time < 1 day: ONLY close if clear negative news or max_acceptable_loss hit
            - Hold time < 1 week: Allow position to develop - daily fluctuations are normal
            
            WHEN TO ACTUALLY CLOSE:
            ✗ Stock dropped 1-2%% today → DO NOT CLOSE (normal volatility)
            ✗ Position red after 1 day → DO NOT CLOSE (give it time)
            ✓ max_acceptable_loss_percent exceeded → CLOSE (your pre-defined limit hit)
            ✓ Earnings miss or significant negative news → CLOSE (thesis invalidated)
            ✓ Sector-wide selloff with no recovery signals → Consider CLOSE
            
            ═══════════════════════════════════════════════════════════════════
            TASK 3: NEW OPPORTUNITIES - AGGRESSIVE 100%%+ ANNUAL RETURN TARGET
            ═══════════════════════════════════════════════════════════════════
            
            AGGRESSIVE STRATEGY - YOU DECIDE EVERYTHING:
            1. YOU decide how many positions to open (no artificial limits)
            2. YOU decide position_size_percent (1-100%% of available capital)
            3. High-conviction (80+) trades: Size aggressively, up to 50-100%%
            4. Medium-conviction (60-79) trades: Size moderately, 10-30%%
            5. LONG only (no short selling)
            6. Only stocks from our Tech/Defense universe
            
            TARGET: 100%%+ annual return - be aggressive with high-conviction opportunities!
            
            Search for new trading opportunities:
            - Look for positive catalysts (earnings beats, upgrades, contracts, products)
            - Conviction must be > 60
            - Prefer stocks with clear momentum and sentiment
            - Size positions based on your conviction - NO ARTIFICIAL LIMITS
            
            ═══════════════════════════════════════════════════════════════════
            PRE-MORTEM REQUIREMENT (CRITICAL FOR SELF-LEARNING!)
            ═══════════════════════════════════════════════════════════════════
            
            For EVERY new opportunity, you MUST include:
            1. pre_mortem: "This trade FAILS if: [specific condition]"
            2. bull_case: Why this trade should succeed
            3. bear_case: Counter-argument (devil's advocate)
            4. expected_hold_hours_min/max: How long you expect to hold (in hours, e.g. 24-168 for days)
            5. target_pnl_percent: Target profit percentage (typically 5-15%% for stocks)
            6. max_acceptable_loss_percent: Maximum acceptable loss (typically 5-10%%)
            
            ═══════════════════════════════════════════════════════════════════
            OUTPUT FORMAT (STRICTLY FOLLOW!)
            ═══════════════════════════════════════════════════════════════════
            
            Respond with a JSON object:
            
            ```json
            {
              "analysis_text": "📊 **Stock Portfolio Update**\\n\\n[Your detailed market analysis. At least 200 words.]",
              
              "market_summary": "Brief summary of the overall market in 1-2 sentences",
              
              "position_decisions": [
                {
                  "symbol": "AAPL",
                  "action": "KEEP",
                  "reason": "Strong earnings beat, analyst upgrades",
                  "current_sentiment": 65,
                  "scale_percent": 0
                },
                {
                  "symbol": "NVDA",
                  "action": "REDUCE",
                  "reason": "Taking profits after 20%% gain, slightly overbought",
                  "current_sentiment": 55,
                  "scale_percent": 30
                }
              ],
              
              "new_opportunities": [
                {
                  "symbol": "RTX",
                  "direction": "LONG",
                  "sector": "DEFENSE",
                  "conviction": 78,
                  "position_size_percent": 25,
                  "sentiment_score": 68,
                  "narrative_strength": 80,
                  "reason": "New defense contract announced, positive analyst coverage",
                  "key_signals": ["Defense contract win", "Analyst upgrade to Buy"],
                  "pre_mortem": "This trade FAILS if: Budget cuts announced or contract delayed/cancelled",
                  "bull_case": "Strong government spending, backlog increasing, margin expansion",
                  "bear_case": "Defense spending concerns, competition from other contractors",
                  "expected_hold_hours_min": 48,
                  "expected_hold_hours_max": 168,
                  "target_pnl_percent": 8,
                  "max_acceptable_loss_percent": 5
                }
              ],
              
              "stocks_analyzed": 15,
              "stocks_skipped": 14
            }
            ```
            
            IMPORTANT:
            - All symbols as NYSE/NASDAQ tickers (e.g. AAPL, RTX, NVDA)
            - sector must be "TECH" or "DEFENSE"
            - position_size_percent is REQUIRED (1-100) - YOU decide based on conviction!
            - scale_percent only used with EXTEND/REDUCE (10-100)
            - pre_mortem, bull_case, bear_case are REQUIRED for new opportunities!
            - LONG only - no SHORT positions allowed
            - TARGET: 100%+ annual return - size aggressively!
            
            ═══════════════════════════════════════════════════════════════════
            ANALYZE NOW - OUTPUT JSON ONLY
            ═══════════════════════════════════════════════════════════════════
            """, timestamp, marketStatus, positionsContext, deploymentInfo);
    }

    private AnalysisResult parseResponse(String response, String rawPrompt) {
        try {
            JsonNode root = objectMapper.readTree(response);
            JsonNode choices = root.get("choices");
            
            if (choices == null || choices.isEmpty()) {
                return AnalysisResult.error("No choices in response", rawPrompt, response);
            }

            String content = choices.get(0).get("message").get("content").asText();
            int tokensUsed = root.has("usage") ? root.get("usage").get("total_tokens").asInt() : 0;

            String jsonContent = extractJson(content);
            JsonNode data = objectMapper.readTree(jsonContent);

            // Parse position decisions
            List<PositionDecision> positionDecisions = new ArrayList<>();
            JsonNode decisionsNode = data.get("position_decisions");
            if (decisionsNode != null && decisionsNode.isArray()) {
                for (JsonNode pd : decisionsNode) {
                    String actionStr = pd.has("action") ? pd.get("action").asText().toUpperCase() : "KEEP";
                    PositionDecision.Action action;
                    try {
                        action = PositionDecision.Action.valueOf(actionStr);
                    } catch (IllegalArgumentException e) {
                        action = PositionDecision.Action.KEEP;
                    }

                    int scalePercent = 0;
                    if (action == PositionDecision.Action.EXTEND || action == PositionDecision.Action.REDUCE) {
                        scalePercent = pd.has("scale_percent") ? pd.get("scale_percent").asInt(50) : 50;
                        scalePercent = Math.max(10, Math.min(100, scalePercent));
                    }

                    positionDecisions.add(PositionDecision.builder()
                            .symbol(pd.has("symbol") ? pd.get("symbol").asText() : "")
                            .action(action)
                            .reason(pd.has("reason") ? pd.get("reason").asText() : "")
                            .currentSentiment(pd.has("current_sentiment") ? pd.get("current_sentiment").asInt() : 0)
                            .scalePercent(scalePercent)
                            .build());
                }
            }

            // Parse new opportunities
            List<NewOpportunity> opportunities = new ArrayList<>();
            JsonNode oppsNode = data.get("new_opportunities");
            if (oppsNode != null && oppsNode.isArray()) {
                for (JsonNode opp : oppsNode) {
                    String dirStr = opp.has("direction") ? opp.get("direction").asText().toUpperCase() : "";
                    // Only LONG allowed for stocks
                    if (!dirStr.equals("LONG")) {
                        continue;
                    }

                    int conviction = opp.has("conviction") ? opp.get("conviction").asInt() : 0;
                    if (conviction < 60) {
                        continue;
                    }

                    List<String> keySignals = new ArrayList<>();
                    if (opp.has("key_signals") && opp.get("key_signals").isArray()) {
                        for (JsonNode signal : opp.get("key_signals")) {
                            keySignals.add(signal.asText());
                        }
                    }

                    String preMortem = opp.has("pre_mortem") ? opp.get("pre_mortem").asText() : null;
                    String bullCase = opp.has("bull_case") ? opp.get("bull_case").asText() : null;
                    String bearCase = opp.has("bear_case") ? opp.get("bear_case").asText() : null;
                    Integer expectedHoldMin = opp.has("expected_hold_hours_min") ? opp.get("expected_hold_hours_min").asInt() : null;
                    Integer expectedHoldMax = opp.has("expected_hold_hours_max") ? opp.get("expected_hold_hours_max").asInt() : null;
                    BigDecimal targetPnl = opp.has("target_pnl_percent") 
                            ? new BigDecimal(opp.get("target_pnl_percent").asText()) : null;
                    BigDecimal maxLoss = opp.has("max_acceptable_loss_percent") 
                            ? new BigDecimal(opp.get("max_acceptable_loss_percent").asText()) : null;
                    
                    // Position size percent determined by Grok (1-100%), no fixed limits
                    Integer positionSizePercent = opp.has("position_size_percent") 
                            ? opp.get("position_size_percent").asInt() : null;

                    opportunities.add(NewOpportunity.builder()
                            .symbol(opp.has("symbol") ? opp.get("symbol").asText() : "")
                            .direction(NewOpportunity.Direction.LONG)
                            .sector(opp.has("sector") ? opp.get("sector").asText() : "OTHER")
                            .conviction(conviction)
                            .positionSizePercent(positionSizePercent)
                            .sentimentScore(opp.has("sentiment_score") ? opp.get("sentiment_score").asInt() : 0)
                            .narrativeStrength(opp.has("narrative_strength") ? opp.get("narrative_strength").asInt() : 0)
                            .reason(opp.has("reason") ? opp.get("reason").asText() : "")
                            .keySignals(keySignals.subList(0, Math.min(5, keySignals.size())))
                            .preMortem(preMortem)
                            .bullCase(bullCase)
                            .bearCase(bearCase)
                            .expectedHoldHoursMin(expectedHoldMin)
                            .expectedHoldHoursMax(expectedHoldMax)
                            .targetPnlPercent(targetPnl)
                            .maxAcceptableLossPercent(maxLoss)
                            .build());
                }
            }

            opportunities.sort((a, b) -> Integer.compare(b.getConviction(), a.getConviction()));

            return AnalysisResult.builder()
                    .analysisText(data.has("analysis_text") ? data.get("analysis_text").asText() : "No analysis text")
                    .marketSummary(data.has("market_summary") ? data.get("market_summary").asText() : "")
                    .positionDecisions(positionDecisions)
                    .newOpportunities(opportunities)
                    .stocksAnalyzed(data.has("stocks_analyzed") ? data.get("stocks_analyzed").asInt() : 0)
                    .stocksSkipped(data.has("stocks_skipped") ? data.get("stocks_skipped").asInt() : 0)
                    .tokensUsed(tokensUsed)
                    .rawPrompt(rawPrompt)
                    .rawResponse(content)
                    .build();

        } catch (Exception e) {
            log.error("Failed to parse Grok response: {}", e.getMessage());
            return AnalysisResult.error("Parse error: " + e.getMessage(), rawPrompt, response);
        }
    }

    private String extractJson(String content) {
        if (content.contains("```json")) {
            int start = content.indexOf("```json") + 7;
            int end = content.indexOf("```", start);
            if (end > start) {
                content = content.substring(start, end).trim();
            }
        } else if (content.contains("```")) {
            int start = content.indexOf("```") + 3;
            int end = content.indexOf("```", start);
            if (end > start) {
                content = content.substring(start, end).trim();
            }
        }

        int jsonStart = content.indexOf("{");
        int jsonEnd = content.lastIndexOf("}") + 1;
        if (jsonStart >= 0 && jsonEnd > jsonStart) {
            content = content.substring(jsonStart, jsonEnd);
        }

        return content;
    }
}

