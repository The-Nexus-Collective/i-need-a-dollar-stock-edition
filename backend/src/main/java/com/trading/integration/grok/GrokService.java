package com.trading.integration.grok;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trading.integration.grok.dto.AnalysisResult;
import com.trading.integration.grok.dto.NewOpportunity;
import com.trading.integration.grok.dto.PositionDecision;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
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

    @Value("${xai.api-key:}")
    private String apiKey;

    @Value("${xai.base-url:https://api.x.ai/v1}")
    private String baseUrl;

    @Value("${xai.model:grok-4-1-fast-reasoning}")
    private String model;

    private final ObjectMapper objectMapper;
    private WebClient webClient;

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
     * Run comprehensive portfolio analysis.
     *
     * @param positionsContext Formatted string of current positions with risk info
     * @param availableSlots   Number of slots available for new positions
     * @param deploymentInfo   Deployment status message
     * @param availableCapital Current available capital
     * @return Complete analysis result with decisions
     */
    public AnalysisResult analyze(String positionsContext, int availableSlots, 
                                   String deploymentInfo, BigDecimal availableCapital) {
        
        String prompt = buildPrompt(positionsContext, availableSlots, deploymentInfo);
        String systemPrompt = getSystemPrompt();
        String fullPrompt = "[SYSTEM]\n" + systemPrompt + "\n\n[USER]\n" + prompt;

        if (apiKey == null || apiKey.isEmpty()) {
            log.warn("Grok API key not configured, returning empty analysis");
            return AnalysisResult.error("API key not configured", fullPrompt, "");
        }

        try {
            log.info("Sending request to Grok API (model: {})...", model);

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

            return result;

        } catch (org.springframework.web.reactive.function.client.WebClientResponseException e) {
            log.error("Grok API error - Status: {}, Body: {}", e.getStatusCode(), e.getResponseBodyAsString());
            return AnalysisResult.error(e.getResponseBodyAsString(), fullPrompt, "");
        } catch (Exception e) {
            log.error("Grok analysis failed: {}", e.getMessage(), e);
            return AnalysisResult.error(e.getMessage(), fullPrompt, "");
        }
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

        return String.format("""
            Du bist ein professioneller Krypto-Portfolio-Manager. Deine Aufgabe ist es, in Echtzeit das Portfolio zu verwalten.
            
            ═══════════════════════════════════════════════════════════════════
            AKTUELLER ZEITPUNKT: %s
            ═══════════════════════════════════════════════════════════════════
            
            ═══════════════════════════════════════════════════════════════════
            AUFGABE 1: MARKTANALYSE (Top 100 Coins)
            ═══════════════════════════════════════════════════════════════════
            
            Analysiere die Top 100 Kryptowährungen nach Marktkapitalisierung, die auf Binance Futures handelbar sind.
            
            WICHTIGE REGELN:
            1. Basiere deine Analyse AUSSCHLIESSLICH auf X-Posts, Reddit-Trends und Markt-Narrativen der LETZTEN 10 MINUTEN
            2. Nutze deine Echtzeit-Suchfunktionen (x_keyword_search, web_search) für aktuelle Daten
            3. Überspringe Coins, bei denen die Datenlage zu dünn oder verrauscht ist - ERZWINGE KEINE BEWERTUNG
            4. Nur Coins mit signifikantem aktuellen Diskussionsvolumen sollen bewertet werden
            
            ═══════════════════════════════════════════════════════════════════
            AUFGABE 2: PORTFOLIO-BEWERTUNG MIT RISIKOMANAGEMENT
            ═══════════════════════════════════════════════════════════════════
            
            %s
            
            %s
            
            ═══════════════════════════════════════════════════════════════════
            RISIKOBEWERTUNG FÜR OFFENE POSITIONEN (WICHTIG!)
            ═══════════════════════════════════════════════════════════════════
            
            Die Positionen oben enthalten detaillierte Risikoangaben. Beachte folgende Regeln:
            
            🔴 DANGER (Margin Risk > 70%%): SOFORT SCHLIESSEN - Position nahe Liquidation!
            🟡 WARNING (Margin Risk 50-70%%): GENAU BEOBACHTEN - Schließen erwägen wenn Sentiment nicht klar bullish
            🟠 ELEVATED (Margin Risk 30-50%%): VORSICHT - Nur halten bei starkem Sentiment
            🟢 OK (Margin Risk < 30%%): Normal weiter analysieren
            
            ZUSÄTZLICHE RISIKOFAKTOREN:
            - PnL < -15%%: Starke Verluste - Stop-Loss prüfen, CLOSE erwägen
            - PnL < -25%%: Kritische Verluste - CLOSE empfohlen außer bei sehr starkem Umkehrsignal
            - Haltezeit > 24h ohne Bewegung: Kapital gebunden - CLOSE wenn kein Katalyst in Sicht
            - Haltezeit > 48h: Prüfen ob besser in andere Opportunitäten investieren
            
            Für jede offene Position entscheide eine der folgenden Aktionen:
            - KEEP: Behalten ohne Änderung
            - CLOSE: Position vollständig schließen (Sentiment gedreht oder Risiko zu hoch)
            - EXTEND: Position aufstocken (Sentiment verstärkt sich, scale_percent = Prozent der aktuellen Größe hinzufügen)
            - REDUCE: Position teilweise schließen (Teilgewinne mitnehmen oder Risiko reduzieren, scale_percent = Prozent zu verkaufen)
            
            ═══════════════════════════════════════════════════════════════════
            LONG UND SHORT STRATEGIE - BEIDE RICHTUNGEN AKTIV NUTZEN!
            ═══════════════════════════════════════════════════════════════════
            
            Du kannst sowohl LONG (auf steigende Kurse) als auch SHORT (auf fallende Kurse) gehen. NUTZE BEIDE RICHTUNGEN AKTIV!
            
            LONG-SIGNALE (bullish):
            - Positive Breaking News, Partnerschaften, Listings
            - Starke Akkumulation durch Whales
            - Bullishes Sentiment auf X/Reddit (>60)
            - Aufwärts-Momentum, neue Hochs
            
            SHORT-SIGNALE (bearish):
            - Negative News: Hacks, Regulierung, Insolvenz, Rug Pull Gerüchte
            - Whale-Verkäufe, große Transfers zu Exchanges
            - Bearishes Sentiment auf X/Reddit (<-30)
            - Abwärts-Momentum, neue Tiefs, Trendbruch
            
            ═══════════════════════════════════════════════════════════════════
            PROFIT-TAKING & CAPITAL ROTATION STRATEGIE
            ═══════════════════════════════════════════════════════════════════
            
            ZIEL: Kapital aktiv aus "erschöpften" Positionen in Trades mit stärkerem Momentum rotieren.
            
            PROAKTIVE REDUCE-REGELN (Gewinne mitnehmen, Kapital freisetzen):
            - +10-20%% PnL + nachlassendes Momentum -> REDUCE 30-40%%
            - +20-40%% PnL + Sentiment unter 50 -> REDUCE 50%%
            - +40%%+ PnL -> REDUCE 50-70%% (unabhängig vom Sentiment)
            
            ═══════════════════════════════════════════════════════════════════
            AUFGABE 3: NEUE OPPORTUNITÄTEN
            ═══════════════════════════════════════════════════════════════════
            
            Verfügbare Slots für neue Positionen: %d
            
            PORTFOLIO-LIMITS:
            1. Positions-Limit: Maximal 50 offene Positionen
            2. Kapital-Limit: Maximal 90%% des Kapitals deployed
            
            Suche nach neuen Trading-Opportunitäten:
            - Nur Coins mit klarem Sentiment-Signal (bullish → LONG, bearish → SHORT)
            - Conviction muss > 60 sein
            
            ═══════════════════════════════════════════════════════════════════
            OUTPUT FORMAT (STRIKT EINHALTEN!)
            ═══════════════════════════════════════════════════════════════════
            
            Antworte mit einem JSON-Objekt:
            
            ```json
            {
              "analysis_text": "📊 **Portfolio-Update**\\n\\n[Deine ausführliche Marktanalyse. Mindestens 200 Wörter.]",
              
              "market_summary": "Kurze Zusammenfassung des Gesamtmarkts in 1-2 Sätzen",
              
              "position_decisions": [
                {
                  "symbol": "BTCUSDT",
                  "action": "KEEP",
                  "reason": "Starkes bullishes Sentiment auf X",
                  "current_sentiment": 65,
                  "scale_percent": 0
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
                  "reason": "Breaking: Avalanche Update, starke Whale-Akkumulation",
                  "key_signals": ["@whale_alert: Large buy", "Avalanche Foundation announcement"]
                }
              ],
              
              "coins_analyzed": 47,
              "coins_skipped": 53
            }
            ```
            
            WICHTIG:
            - Alle Symbole im Binance Futures Format (z.B. BTCUSDT)
            - Leverage zwischen 1-10 basierend auf Conviction
            - scale_percent nur bei EXTEND/REDUCE verwenden (10-100)
            
            ═══════════════════════════════════════════════════════════════════
            JETZT ANALYSIEREN - NUR JSON AUSGEBEN
            ═══════════════════════════════════════════════════════════════════
            """, timestamp, positionsContext, deploymentInfo, availableSlots);
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

                    opportunities.add(NewOpportunity.builder()
                            .symbol(opp.has("symbol") ? opp.get("symbol").asText() : "")
                            .direction(NewOpportunity.Direction.valueOf(dirStr))
                            .conviction(conviction)
                            .leverage(Math.max(1, Math.min(10, opp.has("leverage") ? opp.get("leverage").asInt(3) : 3)))
                            .sentimentScore(opp.has("sentiment_score") ? opp.get("sentiment_score").asInt() : 0)
                            .narrativeStrength(opp.has("narrative_strength") ? opp.get("narrative_strength").asInt() : 0)
                            .reason(opp.has("reason") ? opp.get("reason").asText() : "")
                            .keySignals(keySignals.subList(0, Math.min(5, keySignals.size())))
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

