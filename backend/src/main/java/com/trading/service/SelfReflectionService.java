package com.trading.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trading.entity.Position;
import com.trading.entity.ReflectionEntry;
import com.trading.entity.TradeWisdom;
import com.trading.entity.TradeWisdom.WisdomType;
import com.trading.repository.ReflectionEntryRepository;
import com.trading.repository.TradeWisdomRepository;
import lombok.Builder;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import jakarta.annotation.PostConstruct;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Service for Grok's self-reflection after trades close.
 * 
 * After a trade closes (especially losing trades), asks Grok to reflect:
 * - Was the Pre-Mortem prediction correct?
 * - What lesson should be learned?
 * 
 * Extracts and stores wisdom for future trades.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SelfReflectionService {

    private final TradeWisdomRepository wisdomRepository;
    private final ReflectionEntryRepository reflectionRepository;
    private final ObjectMapper objectMapper;

    @Value("${xai.api-key:}")
    private String apiKey;

    @Value("${xai.base-url:https://api.x.ai/v1}")
    private String baseUrl;

    @Value("${xai.model:grok-4-1-fast-reasoning}")
    private String model;

    private WebClient webClient;

    private static final int TIMEOUT_SECONDS = 60;
    private static final BigDecimal REFLECTION_PNL_THRESHOLD = new BigDecimal("5");

    @PostConstruct
    public void init() {
        this.webClient = WebClient.builder()
                .baseUrl(baseUrl)
                .defaultHeader("Authorization", "Bearer " + apiKey)
                .defaultHeader("Content-Type", "application/json")
                .build();
    }

    @Data
    @Builder
    public static class ReflectionResult {
        private boolean preMortemCorrect;
        private WisdomType wisdomType;
        private String wisdomDescription;
        private String whatHappened;
    }

    /**
     * Reflect on a closed trade.
     * Only reflects on losses or marginal wins (PnL < 5%).
     */
    public void reflectOnTrade(Position closedPosition, BigDecimal exitPrice, String marketContext) {
        if (closedPosition.getPreMortem() == null || closedPosition.getPreMortem().isEmpty()) {
            log.debug("Skipping reflection for {} - no Pre-Mortem recorded", closedPosition.getSymbol());
            return;
        }

        BigDecimal pnlPercent = calculatePnlPercent(closedPosition, exitPrice);
        
        // Only reflect on losses or marginal wins
        if (pnlPercent.compareTo(REFLECTION_PNL_THRESHOLD) > 0) {
            log.debug("Skipping reflection for {} - PnL {}% above threshold", 
                    closedPosition.getSymbol(), pnlPercent);
            return;
        }

        try {
            ReflectionResult result = callGrokForReflection(closedPosition, exitPrice, pnlPercent, marketContext);
            
            // Save or increment wisdom if learned
            if (result.getWisdomDescription() != null && !result.getWisdomDescription().isEmpty()) {
                saveOrIncrementWisdom(result, closedPosition);
            }
            
            // Save reflection entry for timeline
            saveReflectionEntry(closedPosition, exitPrice, pnlPercent, result, marketContext);
            
            log.info("Reflection complete for {}: Pre-Mortem was {} - {}",
                    closedPosition.getSymbol(),
                    result.isPreMortemCorrect() ? "CORRECT" : "INCORRECT",
                    result.getWisdomDescription() != null ? result.getWisdomDescription() : "No new wisdom");
                    
        } catch (Exception e) {
            log.error("Failed to reflect on trade {}: {}", closedPosition.getSymbol(), e.getMessage());
        }
    }

    private ReflectionResult callGrokForReflection(Position position, BigDecimal exitPrice, 
                                                    BigDecimal pnlPercent, String marketContext) {
        Duration holdTime = Duration.between(position.getEntryTime(), 
                position.getExitTime() != null ? position.getExitTime() : Instant.now());
        int holdHours = (int) holdTime.toHours();

        boolean withinExpectedTime = isWithinExpectedTime(position, holdHours);
        String timeAssessment = withinExpectedTime 
                ? "Haltezeit war im erwarteten Bereich"
                : String.format("Haltezeit (%dh) war AUSSERHALB deiner Erwartung (%s)", 
                        holdHours, formatExpectedTime(position));

        String prompt = buildReflectionPrompt(position, exitPrice, pnlPercent, holdHours, 
                timeAssessment, marketContext);

        if (apiKey == null || apiKey.isEmpty()) {
            log.warn("No API key configured, returning default reflection");
            return ReflectionResult.builder()
                    .preMortemCorrect(pnlPercent.compareTo(BigDecimal.ZERO) < 0)
                    .whatHappened(marketContext)
                    .build();
        }

        try {
            Map<String, Object> request = new LinkedHashMap<>();
            request.put("model", model);
            request.put("messages", List.of(
                    Map.of("role", "system", "content", getReflectionSystemPrompt()),
                    Map.of("role", "user", "content", prompt)
            ));
            request.put("temperature", 0.2);
            request.put("max_tokens", 1000);

            String response = webClient.post()
                    .uri("/chat/completions")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(String.class)
                    .timeout(java.time.Duration.ofSeconds(TIMEOUT_SECONDS))
                    .block();

            return parseReflectionResponse(response);

        } catch (Exception e) {
            log.error("Grok reflection call failed: {}", e.getMessage());
            return ReflectionResult.builder()
                    .preMortemCorrect(false)
                    .whatHappened(marketContext)
                    .build();
        }
    }

    private String getReflectionSystemPrompt() {
        return """
            Du bist ein Trading-Coach der Grok dabei hilft, aus vergangenen Trades zu lernen.
            
            Deine Aufgabe:
            1. Bewerte ob das Pre-Mortem des Trades korrekt war
            2. Extrahiere EINE konkrete Lektion (max 20 Worte)
            3. Sei ehrlich und kritisch
            
            Antworte NUR mit validem JSON.""";
    }

    private String buildReflectionPrompt(Position position, BigDecimal exitPrice, 
                                          BigDecimal pnlPercent, int holdHours,
                                          String timeAssessment, String marketContext) {
        String resultEmoji = pnlPercent.compareTo(BigDecimal.ZERO) >= 0 ? "✓" : "✗";
        
        return String.format("""
            ═══════════════════════════════════════════════════════════════════
            SELBSTREFLEXION: Trade Review
            ═══════════════════════════════════════════════════════════════════
            
            DEIN TRADE:
            - %s %s @ %.4f → %.4f
            - Ergebnis: %.1f%% %s
            - Haltezeit: %d Stunden
            - %s
            
            DEIN PRE-MORTEM WAR:
            "%s"
            
            DEIN BEAR CASE WAR:
            "%s"
            
            WAS PASSIERT IST:
            %s
            
            ═══════════════════════════════════════════════════════════════════
            AUFGABE:
            ═══════════════════════════════════════════════════════════════════
            
            Antworte mit diesem JSON Format:
            
            ```json
            {
              "pre_mortem_correct": true/false,
              "explanation": "Kurze Erklärung warum (1-2 Sätze)",
              "wisdom_type": "WARNING_SIGNAL" | "BLIND_SPOT" | "TIME_LESSON" | null,
              "wisdom_description": "Die Lektion in max 20 Worten" | null
            }
            ```
            
            REGELN:
            - pre_mortem_correct = true: Wenn das Pre-Mortem das Ergebnis richtig vorhergesagt hat
            - wisdom_type:
              - WARNING_SIGNAL: Pre-Mortem war korrekt, du hast es aber ignoriert
              - BLIND_SPOT: Ein Risiko das im Pre-Mortem nicht erwähnt wurde
              - TIME_LESSON: Erkenntnis über Haltezeit-Erwartungen
              - null: Kein neues Learning nötig (Trade war erfolgreich oder Pre-Mortem stimmte)
            - wisdom_description: Nur wenn wisdom_type != null, max 20 Worte!
            """,
                position.getDirection(),
                position.getSymbol(),
                position.getEntryPrice(),
                exitPrice,
                pnlPercent,
                resultEmoji,
                holdHours,
                timeAssessment,
                position.getPreMortem() != null ? position.getPreMortem() : "Kein Pre-Mortem",
                position.getBearCase() != null ? position.getBearCase() : "Kein Bear Case",
                marketContext != null ? marketContext : "Keine Details verfügbar");
    }

    private ReflectionResult parseReflectionResponse(String response) {
        try {
            JsonNode root = objectMapper.readTree(response);
            JsonNode choices = root.get("choices");
            
            if (choices == null || choices.isEmpty()) {
                return ReflectionResult.builder().preMortemCorrect(false).build();
            }

            String content = choices.get(0).get("message").get("content").asText();
            
            // Extract JSON from markdown if present
            String jsonContent = extractJson(content);
            JsonNode data = objectMapper.readTree(jsonContent);

            boolean preMortemCorrect = data.has("pre_mortem_correct") && 
                    data.get("pre_mortem_correct").asBoolean();
            
            String explanation = data.has("explanation") ? data.get("explanation").asText() : null;
            
            WisdomType wisdomType = null;
            if (data.has("wisdom_type") && !data.get("wisdom_type").isNull()) {
                String typeStr = data.get("wisdom_type").asText();
                try {
                    wisdomType = WisdomType.valueOf(typeStr);
                } catch (IllegalArgumentException e) {
                    log.warn("Unknown wisdom type: {}", typeStr);
                }
            }
            
            String wisdomDescription = null;
            if (data.has("wisdom_description") && !data.get("wisdom_description").isNull()) {
                wisdomDescription = data.get("wisdom_description").asText();
            }

            return ReflectionResult.builder()
                    .preMortemCorrect(preMortemCorrect)
                    .wisdomType(wisdomType)
                    .wisdomDescription(wisdomDescription)
                    .whatHappened(explanation)
                    .build();

        } catch (Exception e) {
            log.error("Failed to parse reflection response: {}", e.getMessage());
            return ReflectionResult.builder().preMortemCorrect(false).build();
        }
    }

    private String extractJson(String content) {
        if (content.contains("```json")) {
            int start = content.indexOf("```json") + 7;
            int end = content.indexOf("```", start);
            if (end > start) {
                return content.substring(start, end).trim();
            }
        } else if (content.contains("```")) {
            int start = content.indexOf("```") + 3;
            int end = content.indexOf("```", start);
            if (end > start) {
                return content.substring(start, end).trim();
            }
        }
        
        int jsonStart = content.indexOf("{");
        int jsonEnd = content.lastIndexOf("}") + 1;
        if (jsonStart >= 0 && jsonEnd > jsonStart) {
            return content.substring(jsonStart, jsonEnd);
        }
        
        return content;
    }

    private void saveOrIncrementWisdom(ReflectionResult result, Position position) {
        if (result.getWisdomType() == null || result.getWisdomDescription() == null) {
            return;
        }

        // Try to find existing similar wisdom
        List<TradeWisdom> existing = wisdomRepository.findByDescriptionContaining(
                result.getWisdomDescription().substring(0, Math.min(20, result.getWisdomDescription().length())));
        
        if (!existing.isEmpty()) {
            // Increment existing wisdom
            TradeWisdom wisdom = existing.get(0);
            wisdom.incrementOccurrence();
            wisdomRepository.save(wisdom);
            log.info("Incremented wisdom occurrence: {} (now {}x)", 
                    wisdom.getDescription(), wisdom.getOccurrences());
        } else {
            // Create new wisdom
            TradeWisdom wisdom = TradeWisdom.builder()
                    .id(UUID.randomUUID().toString())
                    .type(result.getWisdomType())
                    .description(result.getWisdomDescription())
                    .occurrences(1)
                    .firstOccurred(Instant.now())
                    .lastOccurred(Instant.now())
                    .symbolPattern(extractSymbolPattern(position.getSymbol()))
                    .directionPattern(position.getDirection())
                    .build();
            wisdomRepository.save(wisdom);
            log.info("Created new wisdom: {}", wisdom.getDescription());
        }
    }

    private void saveReflectionEntry(Position position, BigDecimal exitPrice, 
                                      BigDecimal pnlPercent, ReflectionResult result, 
                                      String marketContext) {
        Duration holdTime = Duration.between(position.getEntryTime(), 
                position.getExitTime() != null ? position.getExitTime() : Instant.now());
        
        ReflectionEntry entry = ReflectionEntry.builder()
                .id(UUID.randomUUID().toString())
                .positionId(position.getId())
                .symbol(position.getSymbol())
                .direction(position.getDirection())
                .entryPrice(position.getEntryPrice())
                .exitPrice(exitPrice)
                .pnlPercent(pnlPercent)
                .holdHours((int) holdTime.toHours())
                .preMortem(position.getPreMortem())
                .whatHappened(result.getWhatHappened() != null ? result.getWhatHappened() : marketContext)
                .preMortemWasCorrect(result.isPreMortemCorrect())
                .lessonType(result.getWisdomType())
                .lessonLearned(result.getWisdomDescription())
                .reflectedAt(Instant.now())
                .build();
        
        reflectionRepository.save(entry);
    }

    private BigDecimal calculatePnlPercent(Position position, BigDecimal exitPrice) {
        if (exitPrice == null || position.getEntryPrice() == null || 
            position.getSizeUsdt() == null || position.getSizeUsdt().compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        
        BigDecimal priceDiff;
        if ("LONG".equalsIgnoreCase(position.getDirection())) {
            priceDiff = exitPrice.subtract(position.getEntryPrice());
        } else {
            priceDiff = position.getEntryPrice().subtract(exitPrice);
        }
        
        BigDecimal pnl = priceDiff.multiply(position.getQuantity());
        return pnl.divide(position.getSizeUsdt(), 4, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));
    }

    private boolean isWithinExpectedTime(Position position, int holdHours) {
        if (position.getExpectedHoldHoursMin() == null && position.getExpectedHoldHoursMax() == null) {
            return true; // No expectation set
        }
        
        boolean minOk = position.getExpectedHoldHoursMin() == null || 
                holdHours >= position.getExpectedHoldHoursMin();
        boolean maxOk = position.getExpectedHoldHoursMax() == null || 
                holdHours <= position.getExpectedHoldHoursMax();
        
        return minOk && maxOk;
    }

    private String formatExpectedTime(Position position) {
        if (position.getExpectedHoldHoursMin() == null && position.getExpectedHoldHoursMax() == null) {
            return "keine Erwartung";
        }
        if (position.getExpectedHoldHoursMin() != null && position.getExpectedHoldHoursMax() != null) {
            return position.getExpectedHoldHoursMin() + "-" + position.getExpectedHoldHoursMax() + "h";
        }
        if (position.getExpectedHoldHoursMin() != null) {
            return "min " + position.getExpectedHoldHoursMin() + "h";
        }
        return "max " + position.getExpectedHoldHoursMax() + "h";
    }

    private String extractSymbolPattern(String symbol) {
        // Extract base pattern (e.g., "BTC" from "BTCUSDT")
        if (symbol == null) return null;
        if (symbol.endsWith("USDT")) {
            return symbol.substring(0, symbol.length() - 4);
        }
        return symbol;
    }
}

