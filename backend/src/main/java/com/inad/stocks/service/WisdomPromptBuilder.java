package com.inad.stocks.service;

import com.inad.stocks.entity.TradeWisdom;
import com.inad.stocks.entity.TradeWisdom.WisdomType;
import com.inad.stocks.repository.TradeWisdomRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Service to build the wisdom section for Grok's prompt.
 * 
 * Formats accumulated learnings (warnings, blind spots, time lessons)
 * into a prompt section that reminds Grok of past mistakes.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class WisdomPromptBuilder {

    private final TradeWisdomRepository wisdomRepository;

    private static final int MAX_WARNINGS = 5;
    private static final int MAX_BLIND_SPOTS = 3;
    private static final int MAX_TIME_LESSONS = 2;

    /**
     * Build the wisdom section for the Grok prompt.
     * Returns empty string if no wisdom accumulated yet.
     */
    public String buildWisdomSection() {
        List<TradeWisdom> warnings = wisdomRepository.findTopByTypeOrderByOccurrencesDesc(
                WisdomType.WARNING_SIGNAL, MAX_WARNINGS);
        List<TradeWisdom> blindSpots = wisdomRepository.findTopByTypeOrderByOccurrencesDesc(
                WisdomType.BLIND_SPOT, MAX_BLIND_SPOTS);
        List<TradeWisdom> timeLessons = wisdomRepository.findTopByTypeOrderByOccurrencesDesc(
                WisdomType.TIME_LESSON, MAX_TIME_LESSONS);

        if (warnings.isEmpty() && blindSpots.isEmpty() && timeLessons.isEmpty()) {
            return "";
        }

        StringBuilder sb = new StringBuilder();
        sb.append("""
            
            ═══════════════════════════════════════════════════════════════════
            DEINE BISHERIGEN ERKENNTNISSE (aus eigenen Fehlern gelernt)
            ═══════════════════════════════════════════════════════════════════
            
            """);

        if (!warnings.isEmpty()) {
            sb.append("⚠️ WARNSIGNALE DIE DU UNTERSCHÄTZT HAST:\n");
            for (int i = 0; i < warnings.size(); i++) {
                TradeWisdom w = warnings.get(i);
                sb.append(String.format("   %d. \"%s\" (%dx eingetreten)\n",
                        i + 1, w.getDescription(), w.getOccurrences()));
            }
            sb.append("\n");
        }

        if (!blindSpots.isEmpty()) {
            sb.append("🔍 BLINDE FLECKEN:\n");
            for (int i = 0; i < blindSpots.size(); i++) {
                TradeWisdom w = blindSpots.get(i);
                sb.append(String.format("   %d. \"%s\" (%dx übersehen)\n",
                        i + 1, w.getDescription(), w.getOccurrences()));
            }
            sb.append("\n");
        }

        if (!timeLessons.isEmpty()) {
            sb.append("⏱️ ZEIT-LEARNINGS:\n");
            for (int i = 0; i < timeLessons.size(); i++) {
                TradeWisdom w = timeLessons.get(i);
                sb.append(String.format("   %d. \"%s\"\n", i + 1, w.getDescription()));
            }
            sb.append("\n");
        }

        sb.append("BEACHTE DIESE ERKENNTNISSE BEI DEINER AKTUELLEN ANALYSE!\n\n");

        return sb.toString();
    }

    /**
     * Get count of total accumulated wisdoms.
     */
    public long getTotalWisdomCount() {
        return wisdomRepository.count();
    }

    /**
     * Check if any wisdom has been accumulated.
     */
    public boolean hasWisdom() {
        return wisdomRepository.count() > 0;
    }
}

