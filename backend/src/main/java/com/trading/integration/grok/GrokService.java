package com.trading.integration.grok;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trading.integration.grok.dto.AnalysisResult;
import com.trading.integration.grok.dto.NewOpportunity;
import com.trading.integration.grok.dto.PositionDecision;
import com.trading.service.WisdomPromptBuilder;
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
 * Comprehensive Grok AI Service for portfolio management.
 * 
 * Uses Grok's real-time capabilities to:
 * 1. Identify top 100 coins by market cap
 * 2. Search X/Reddit for last 10 minutes sentiment
 * 3. Evaluate open positions (KEEP, CLOSE, EXTEND, REDUCE)
 * 4. Find new opportunities (LONG/SHORT with conviction)
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
    private WisdomPromptBuilder wisdomPromptBuilder;

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
     *
     * @param positionsContext Formatted string of current positions with risk info
     * @param availableSlots   Number of slots available for new positions
     * @param deploymentInfo   Deployment status message
     * @param availableCapital Current available capital
     * @return Complete analysis result with decisions
     */
    public AnalysisResult analyze(String positionsContext, int availableSlots, 
                                   String deploymentInfo, BigDecimal availableCapital) {
        return analyzeWithRetry(positionsContext, availableSlots, deploymentInfo, availableCapital, 1);
    }

    /**
     * Internal method that performs analysis with retry logic for empty responses.
     */
    private AnalysisResult analyzeWithRetry(String positionsContext, int availableSlots,
                                            String deploymentInfo, BigDecimal availableCapital, int attempt) {
        
        String prompt = buildPrompt(positionsContext, availableSlots, deploymentInfo);
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

            // Check if response is empty and retry if needed
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
                
                return analyzeWithRetry(positionsContext, availableSlots, deploymentInfo, availableCapital, attempt + 1);
            }

            if (isEmptyAnalysis(result)) {
                log.warn("Grok returned empty analysis after {} attempts. Final response: {}", 
                         attempt, result.getRawResponse());
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

    /**
     * Check if the analysis result is empty (no coins analyzed and no decisions).
     */
    private boolean isEmptyAnalysis(AnalysisResult result) {
        return result.getCoinsAnalyzed() == 0 
            && result.getNewOpportunities().isEmpty() 
            && result.getPositionDecisions().isEmpty();
    }

    private String getSystemPrompt() {
        return """
            You are a professional crypto portfolio manager with real-time access to market data.
            
            CRITICAL: You MUST use your search tools (x_keyword_search, x_semantic_search, web_search) 
            to gather CURRENT data from the last 10 minutes.
            
            Your internal knowledge is outdated. Only real-time search results matter.
            
            Always output valid JSON as specified in the prompt.""";
    }

    private String buildPrompt(String positionsContext, int availableSlots, String deploymentInfo) {
        String timestamp = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm 'UTC'")
                .withZone(ZoneOffset.UTC)
                .format(Instant.now());
        
        // Include accumulated wisdom if available
        String wisdomSection = "";
        if (wisdomPromptBuilder != null && wisdomPromptBuilder.hasWisdom()) {
            wisdomSection = wisdomPromptBuilder.buildWisdomSection();
            log.info("Including {} accumulated wisdoms in prompt", wisdomPromptBuilder.getTotalWisdomCount());
        }

        return String.format("""
            You are a professional crypto portfolio manager. Your task is to manage the portfolio in real-time.
            
            ═══════════════════════════════════════════════════════════════════
            CURRENT TIME: %s
            ═══════════════════════════════════════════════════════════════════
            
            ═══════════════════════════════════════════════════════════════════
            TASK 1: MARKET ANALYSIS (Top 100 Coins)
            ═══════════════════════════════════════════════════════════════════
            
            Analyze the top 100 cryptocurrencies by market cap that are tradable on Binance Futures.
            
            IMPORTANT RULES:
            1. Base your analysis EXCLUSIVELY on X posts, Reddit trends, and market narratives from the LAST 10 MINUTES
            2. Use your real-time search functions (x_keyword_search, web_search) for current data
            3. Skip coins where data is too thin or noisy - DO NOT FORCE A RATING
            4. Only coins with significant current discussion volume should be rated
            
            ═══════════════════════════════════════════════════════════════════
            TASK 2: PORTFOLIO EVALUATION WITH RISK MANAGEMENT
            ═══════════════════════════════════════════════════════════════════
            
            %s
            
            %s
            
            ═══════════════════════════════════════════════════════════════════
            RISK ASSESSMENT FOR OPEN POSITIONS (IMPORTANT!)
            ═══════════════════════════════════════════════════════════════════
            
            The positions above contain detailed risk data. Follow these rules:
            
            🔴 DANGER (Margin Risk > 70%%): CLOSE IMMEDIATELY - Position near liquidation!
            🟡 WARNING (Margin Risk 50-70%%): WATCH CLOSELY - Consider closing if sentiment not clearly bullish
            🟠 ELEVATED (Margin Risk 30-50%%): CAUTION - Only hold with strong sentiment
            🟢 OK (Margin Risk < 30%%): Continue normal analysis
            
            ADDITIONAL RISK FACTORS:
            - PnL < -15%%: Heavy losses - Check stop-loss, consider CLOSE
            - PnL < -25%%: Critical losses - CLOSE recommended unless very strong reversal signal
            - Hold time > 24h without movement: Capital locked - CLOSE if no catalyst in sight
            - Hold time > 48h: Check if better to rotate into other opportunities
            
            ═══════════════════════════════════════════════════════════════════
            PRE-MORTEM HEALTH CHECK (SELF-LEARNING FEEDBACK!)
            ═══════════════════════════════════════════════════════════════════
            
            If a PRE-MORTEM HEALTH CHECK section is provided above, it shows how your
            predictions from when you opened each trade are comparing to reality NOW.
            
            INTERPRET THE HEALTH CHECK:
            🔴 DANGER: Your max acceptable loss has been exceeded - YOU WERE WRONG
               → Close immediately unless there's a very strong reversal signal
               → Learn from the Bear Case you wrote - was it what happened?
            
            🟡 WARNING: Position approaching limits or exceeding expected hold time
               → Review carefully - is your original thesis still valid?
               → Consider reducing position size
            
            🟢 HEALTHY: Position performing within your expectations
               → If exceeding target PnL - consider TAKE_PROFIT (REDUCE)
               → Continue monitoring
            
            THIS IS YOUR OWN FEEDBACK! Use it to make better decisions.
            
            For each open position, decide one of the following actions:
            - KEEP: Hold without changes
            - CLOSE: Close position completely (sentiment reversed or risk too high)
            - EXTEND: Add to position (sentiment strengthening, scale_percent = percent of current size to add)
            - REDUCE: Partially close position (take partial profits or reduce risk, scale_percent = percent to sell)
            - INCREASE_LEVERAGE: Reduce margin buffer, accept higher liquidation risk (target_leverage = new leverage)
            - DECREASE_LEVERAGE: Increase margin buffer, safer liquidation distance (target_leverage = new leverage)
            
            ═══════════════════════════════════════════════════════════════════
            LEVERAGE MANAGEMENT
            ═══════════════════════════════════════════════════════════════════
            
            IMPORTANT: Changing leverage does NOT change position size or exposure!
            It only adjusts margin allocation:
            - Liquidation Distance (closer/further from current price)
            - ROE%% (Return on Equity - higher/lower based on margin)
            - Available Capital (more/less free for other trades)
            
            INCREASE_LEVERAGE (e.g., 3x → 10x):
            - When: Position in profit, high conviction, strong trend
            - Effect: Less margin locked, liq price closer, ROE%% increases
            - Risk: Higher liquidation risk
            - Benefit: More free capital for other opportunities
            
            DECREASE_LEVERAGE (e.g., 10x → 3x):
            - When: Margin risk increasing but don't want to close
            - Effect: More margin locked, liq price further, ROE%% decreases
            - Risk: More capital locked
            - Benefit: Safer liquidation distance
            
            WHEN TO USE LEVERAGE CHANGE INSTEAD OF CLOSE/REDUCE:
            - Margin Risk 50-70%%, still bullish → DECREASE_LEVERAGE (not CLOSE)
            - Margin Risk > 70%% → CLOSE (too dangerous for leverage change)
            - +30%% PnL, trend intact → INCREASE_LEVERAGE (free up margin)
            - Low free capital → INCREASE_LEVERAGE on winning positions
            
            ═══════════════════════════════════════════════════════════════════
            LONG AND SHORT STRATEGY - ACTIVELY USE BOTH DIRECTIONS!
            ═══════════════════════════════════════════════════════════════════
            
            You can go both LONG (betting on rising prices) and SHORT (betting on falling prices). USE BOTH DIRECTIONS ACTIVELY!
            
            LONG SIGNALS (bullish):
            - Positive breaking news, partnerships, listings
            - Strong whale accumulation
            - Bullish sentiment on X/Reddit (>60)
            - Upward momentum, new highs
            
            SHORT SIGNALS (bearish):
            - Negative news: Hacks, regulation, insolvency, rug pull rumors
            - Whale selling, large transfers to exchanges
            - Bearish sentiment on X/Reddit (<-30)
            - Downward momentum, new lows, trend break
            
            ═══════════════════════════════════════════════════════════════════
            PROFIT-TAKING & CAPITAL ROTATION STRATEGY
            ═══════════════════════════════════════════════════════════════════
            
            GOAL: Actively rotate capital from "exhausted" positions into trades with stronger momentum.
            
            PROACTIVE REDUCE RULES (take profits, free up capital):
            - +10-20%% PnL + fading momentum -> REDUCE 30-40%%
            - +20-40%% PnL + sentiment below 50 -> REDUCE 50%%
            - +40%%+ PnL -> REDUCE 50-70%% (regardless of sentiment)
            
            ═══════════════════════════════════════════════════════════════════
            TASK 3: NEW OPPORTUNITIES
            ═══════════════════════════════════════════════════════════════════
            
            Available slots for new positions: %d
            
            PORTFOLIO LIMITS:
            1. Position limit: Maximum 50 open positions
            2. Capital limit: Maximum 90%% of capital deployed
            
            Search for new trading opportunities:
            - Only coins with clear sentiment signal (bullish → LONG, bearish → SHORT)
            - Conviction must be > 60
            
            ═══════════════════════════════════════════════════════════════════
            PRE-MORTEM REQUIREMENT (CRITICAL FOR SELF-LEARNING!)
            ═══════════════════════════════════════════════════════════════════
            
            For EVERY new opportunity, you MUST include:
            1. pre_mortem: "This trade FAILS if: [specific condition]"
            2. bull_case: Why this trade should succeed
            3. bear_case: Counter-argument (devil's advocate)
            4. expected_hold_hours_min/max: How long you expect to hold
            5. target_pnl_percent: Target profit percentage
            6. max_acceptable_loss_percent: Maximum acceptable loss
            
            This data helps you learn from your mistakes!
            
            ═══════════════════════════════════════════════════════════════════
            OUTPUT FORMAT (STRICTLY FOLLOW!)
            ═══════════════════════════════════════════════════════════════════
            
            Respond with a JSON object:
            
            ```json
            {
              "analysis_text": "📊 **Portfolio Update**\\n\\n[Your detailed market analysis. At least 200 words.]",
              
              "market_summary": "Brief summary of the overall market in 1-2 sentences",
              
              "position_decisions": [
                {
                  "symbol": "BTCUSDT",
                  "action": "KEEP",
                  "reason": "Strong bullish sentiment on X",
                  "current_sentiment": 65,
                  "scale_percent": 0,
                  "target_leverage": 0
                },
                {
                  "symbol": "ETHUSDT",
                  "action": "DECREASE_LEVERAGE",
                  "reason": "Margin risk at 55%%, reducing leverage for safety",
                  "current_sentiment": 45,
                  "scale_percent": 0,
                  "target_leverage": 3
                }
              ],
              
              "new_opportunities": [
                {
                  "symbol": "AVAXUSDT",
                  "direction": "LONG",
                  "conviction": 82,
                  "leverage": 5,
                  "sentiment_score": 72,
                  "narrative_strength": 85,
                  "reason": "Breaking: Avalanche update, strong whale accumulation",
                  "key_signals": ["@whale_alert: Large buy", "Avalanche Foundation announcement"],
                  "pre_mortem": "This trade FAILS if: BTC drops below 65k causing altcoin cascade, or if whale selling resumes within 4h",
                  "bull_case": "Strong institutional interest, partnership announcement pending, volume spike indicates accumulation",
                  "bear_case": "Overbought on 4h RSI, resistance at $45, general market weakness",
                  "expected_hold_hours_min": 4,
                  "expected_hold_hours_max": 24,
                  "target_pnl_percent": 15,
                  "max_acceptable_loss_percent": 10
                }
              ],
              
              "coins_analyzed": 47,
              "coins_skipped": 53
            }
            ```
            
            IMPORTANT:
            - All symbols in Binance Futures format (e.g. BTCUSDT)
            - Leverage between 1-10 based on conviction for NEW positions
            - scale_percent only used with EXTEND/REDUCE (10-100)
            - target_leverage only used with INCREASE_LEVERAGE/DECREASE_LEVERAGE (1-125)
            - pre_mortem, bull_case, bear_case are REQUIRED for new opportunities!
            %s
            ═══════════════════════════════════════════════════════════════════
            ANALYZE NOW - OUTPUT JSON ONLY
            ═══════════════════════════════════════════════════════════════════
            """, timestamp, positionsContext, deploymentInfo, availableSlots, wisdomSection);
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

            // Extract JSON from markdown code block if present
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
                    
                    int targetLeverage = 0;
                    if (action == PositionDecision.Action.INCREASE_LEVERAGE || 
                        action == PositionDecision.Action.DECREASE_LEVERAGE) {
                        targetLeverage = pd.has("target_leverage") ? pd.get("target_leverage").asInt(5) : 5;
                        targetLeverage = Math.max(1, Math.min(125, targetLeverage));
                    }

                    positionDecisions.add(PositionDecision.builder()
                            .symbol(pd.has("symbol") ? pd.get("symbol").asText() : "")
                            .action(action)
                            .reason(pd.has("reason") ? pd.get("reason").asText() : "")
                            .currentSentiment(pd.has("current_sentiment") ? pd.get("current_sentiment").asInt() : 0)
                            .scalePercent(scalePercent)
                            .targetLeverage(targetLeverage)
                            .build());
                }
            }

            // Parse new opportunities
            List<NewOpportunity> opportunities = new ArrayList<>();
            JsonNode oppsNode = data.get("new_opportunities");
            if (oppsNode != null && oppsNode.isArray()) {
                for (JsonNode opp : oppsNode) {
                    String dirStr = opp.has("direction") ? opp.get("direction").asText().toUpperCase() : "";
                    if (!dirStr.equals("LONG") && !dirStr.equals("SHORT")) {
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

                    // Parse Pre-Mortem fields
                    String preMortem = opp.has("pre_mortem") ? opp.get("pre_mortem").asText() : null;
                    String bullCase = opp.has("bull_case") ? opp.get("bull_case").asText() : null;
                    String bearCase = opp.has("bear_case") ? opp.get("bear_case").asText() : null;
                    Integer expectedHoldMin = opp.has("expected_hold_hours_min") ? opp.get("expected_hold_hours_min").asInt() : null;
                    Integer expectedHoldMax = opp.has("expected_hold_hours_max") ? opp.get("expected_hold_hours_max").asInt() : null;
                    BigDecimal targetPnl = opp.has("target_pnl_percent") 
                            ? new BigDecimal(opp.get("target_pnl_percent").asText()) : null;
                    BigDecimal maxLoss = opp.has("max_acceptable_loss_percent") 
                            ? new BigDecimal(opp.get("max_acceptable_loss_percent").asText()) : null;

                    opportunities.add(NewOpportunity.builder()
                            .symbol(opp.has("symbol") ? opp.get("symbol").asText() : "")
                            .direction(NewOpportunity.Direction.valueOf(dirStr))
                            .conviction(conviction)
                            .leverage(Math.max(1, Math.min(10, opp.has("leverage") ? opp.get("leverage").asInt(3) : 3)))
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

            // Sort opportunities by conviction
            opportunities.sort((a, b) -> Integer.compare(b.getConviction(), a.getConviction()));

            return AnalysisResult.builder()
                    .analysisText(data.has("analysis_text") ? data.get("analysis_text").asText() : "No analysis text")
                    .marketSummary(data.has("market_summary") ? data.get("market_summary").asText() : "")
                    .positionDecisions(positionDecisions)
                    .newOpportunities(opportunities)
                    .coinsAnalyzed(data.has("coins_analyzed") ? data.get("coins_analyzed").asInt() : 0)
                    .coinsSkipped(data.has("coins_skipped") ? data.get("coins_skipped").asInt() : 0)
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
        // Extract JSON from markdown code block if present
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

        // Find JSON object boundaries
        int jsonStart = content.indexOf("{");
        int jsonEnd = content.lastIndexOf("}") + 1;
        if (jsonStart >= 0 && jsonEnd > jsonStart) {
            content = content.substring(jsonStart, jsonEnd);
        }

        return content;
    }
}

