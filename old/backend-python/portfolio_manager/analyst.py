"""
Grok Analyst - Single Grok call that does everything

Uses Grok's real-time capabilities to:
1. Identify top 100 coins by market cap
2. Search X/Reddit for last 10 minutes sentiment
3. Evaluate open positions (KEEP or CLOSE)
4. Find new opportunities (LONG/SHORT with conviction)

Returns both human-readable text AND structured JSON.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PositionDecision:
    """
    Grok's decision for an existing position.
    
    Actions:
    - KEEP: Hold position unchanged
    - CLOSE: Fully close the position
    - EXTEND: Add to the position (scale_percent = % of current size to add)
    - REDUCE: Partially close (scale_percent = % of current size to sell)
    """
    symbol: str
    action: str  # "KEEP", "CLOSE", "EXTEND", or "REDUCE"
    reason: str
    current_sentiment: int  # -100 to +100
    scale_percent: int = 0  # For EXTEND/REDUCE: percentage to scale (e.g., 50 = 50%)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "reason": self.reason,
            "current_sentiment": self.current_sentiment,
            "scale_percent": self.scale_percent,
        }


@dataclass
class NewOpportunity:
    """Grok's recommendation for a new trade."""
    symbol: str
    direction: str  # "LONG" or "SHORT"
    conviction: int  # 0-100
    leverage: int  # 1-10
    sentiment_score: int  # -100 to +100
    narrative_strength: int  # 0-100
    reason: str
    key_signals: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "conviction": self.conviction,
            "leverage": self.leverage,
            "sentiment_score": self.sentiment_score,
            "narrative_strength": self.narrative_strength,
            "reason": self.reason,
            "key_signals": self.key_signals,
        }


@dataclass
class AnalysisResult:
    """Complete result from Grok analysis."""
    
    # Human-readable analysis (stored in logbook)
    analysis_text: str
    market_summary: str
    
    # Structured decisions
    position_decisions: List[PositionDecision]
    new_opportunities: List[NewOpportunity]
    
    # Metadata
    coins_analyzed: int
    coins_skipped: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tokens_used: int = 0
    
    # Debug: raw Grok prompt and response
    raw_prompt: str = ""
    raw_response: str = ""
    
    def to_dict(self) -> dict:
        return {
            "analysis_text": self.analysis_text,
            "market_summary": self.market_summary,
            "position_decisions": [d.to_dict() for d in self.position_decisions],
            "new_opportunities": [o.to_dict() for o in self.new_opportunities],
            "coins_analyzed": self.coins_analyzed,
            "coins_skipped": self.coins_skipped,
            "timestamp": self.timestamp.isoformat(),
            "tokens_used": self.tokens_used,
            "raw_prompt": self.raw_prompt,
            "raw_response": self.raw_response,
        }
    
    def get_positions_to_close(self) -> List[str]:
        """Get symbols that Grok recommends closing."""
        return [d.symbol for d in self.position_decisions if d.action == "CLOSE"]
    
    def get_positions_to_keep(self) -> List[str]:
        """Get symbols that Grok recommends keeping."""
        return [d.symbol for d in self.position_decisions if d.action == "KEEP"]
    
    def get_positions_to_extend(self) -> List[PositionDecision]:
        """Get positions that Grok recommends extending."""
        return [d for d in self.position_decisions if d.action == "EXTEND"]
    
    def get_positions_to_reduce(self) -> List[PositionDecision]:
        """Get positions that Grok recommends reducing."""
        return [d for d in self.position_decisions if d.action == "REDUCE"]


class GrokAnalyst:
    """
    Single Grok call that handles all analysis.
    
    Grok internally:
    - Finds top 100 coins by market cap
    - Searches X/Reddit from last 10 minutes
    - Evaluates positions and finds opportunities
    """
    
    XAI_BASE_URL = "https://api.x.ai/v1"
    MODEL = "grok-3"
    
    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
        
        if not self.api_key:
            logger.warning("XAI_API_KEY not set - analyst will fail!")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=300.0,  # 5 minute timeout for comprehensive analysis
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._client
    
    def _build_prompt(self, positions_context: str, available_slots: int, deployment_info: str = "") -> str:
        """Build the comprehensive analysis prompt."""
        
        now = datetime.utcnow()
        timestamp = now.strftime("%Y-%m-%d %H:%M UTC")
        
        return f"""Du bist ein professioneller Krypto-Portfolio-Manager. Deine Aufgabe ist es, in Echtzeit das Portfolio zu verwalten.

═══════════════════════════════════════════════════════════════════
AKTUELLER ZEITPUNKT: {timestamp}
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

{positions_context}

{deployment_info}

═══════════════════════════════════════════════════════════════════
RISIKOBEWERTUNG FÜR OFFENE POSITIONEN (WICHTIG!)
═══════════════════════════════════════════════════════════════════

Die Positionen oben enthalten detaillierte Risikoangaben. Beachte folgende Regeln:

🔴 DANGER (Margin Risk > 70%): SOFORT SCHLIESSEN - Position nahe Liquidation!
🟡 WARNING (Margin Risk 50-70%): GENAU BEOBACHTEN - Schließen erwägen wenn Sentiment nicht klar bullish
🟠 ELEVATED (Margin Risk 30-50%): VORSICHT - Nur halten bei starkem Sentiment
🟢 OK (Margin Risk < 30%): Normal weiter analysieren

ZUSÄTZLICHE RISIKOFAKTOREN:
- PnL < -15%: Starke Verluste - Stop-Loss prüfen, CLOSE erwägen
- PnL < -25%: Kritische Verluste - CLOSE empfohlen außer bei sehr starkem Umkehrsignal
- Haltezeit > 24h ohne Bewegung: Kapital gebunden - CLOSE wenn kein Katalyst in Sicht
- Haltezeit > 48h: Prüfen ob besser in andere Opportunitäten investieren

Für jede offene Position entscheide eine der folgenden Aktionen:
- KEEP: Behalten ohne Änderung
- CLOSE: Position vollständig schließen (Sentiment gedreht oder Risiko zu hoch)
- EXTEND: Position aufstocken (Sentiment verstärkt sich, scale_percent = Prozent der aktuellen Größe hinzufügen)
- REDUCE: Position teilweise schließen (Teilgewinne mitnehmen oder Risiko reduzieren, scale_percent = Prozent zu verkaufen)

EXTEND verwenden wenn:
- Starkes positives Momentum und Sentiment
- Position bereits im Gewinn und Trend bestätigt sich
- Conviction für den Trade erhöht sich
- Margin Risk < 30% (grüner Bereich)

REDUCE verwenden wenn:
- Gute Gewinne vorhanden, aber Unsicherheit steigt
- Teilgewinne mitnehmen bei 20%+ PnL
- Risiko reduzieren ohne Position ganz zu schließen
- Margin Risk im ELEVATED Bereich (30-50%)

═══════════════════════════════════════════════════════════════════
LONG UND SHORT STRATEGIE - BEIDE RICHTUNGEN AKTIV NUTZEN!
═══════════════════════════════════════════════════════════════════

Du kannst sowohl LONG (auf steigende Kurse) als auch SHORT (auf fallende 
Kurse) gehen. NUTZE BEIDE RICHTUNGEN AKTIV!

LONG-SIGNALE (bullish):
- Positive Breaking News, Partnerschaften, Listings
- Starke Akkumulation durch Whales
- Bullishes Sentiment auf X/Reddit (>60)
- Aufwärts-Momentum, neue Hochs
- FOMO-Indikatoren (breite Retail-Aufmerksamkeit)

SHORT-SIGNALE (bearish):
- Negative News: Hacks, Regulierung, Insolvenz, Rug Pull Gerüchte
- Whale-Verkäufe, große Transfers zu Exchanges
- Bearishes Sentiment auf X/Reddit (<-30)
- Abwärts-Momentum, neue Tiefs, Trendbruch
- Überhitzung nach Pump (RSI überkauft, Erschöpfung)
- FUD-Kampagnen, koordinierte Kritik

WANN SHORT BEVORZUGEN:
- Gesamtmarkt bearish (BTC/ETH fallen)
- Coin hat gerade stark gepumpt ohne fundamentalen Grund
- Negative Nachrichten mit Substanz (nicht nur FUD)
- Sentiment dreht von positiv zu negativ

WICHTIG: Ein ausgewogenes Portfolio hat SOWOHL Long- als auch Short-
Positionen! In einem Bärenmarkt können Shorts die Hauptgewinnquelle sein.

═══════════════════════════════════════════════════════════════════
PROFIT-TAKING & CAPITAL ROTATION STRATEGIE
═══════════════════════════════════════════════════════════════════

ZIEL: Kapital aktiv aus "erschöpften" Positionen in Trades mit stärkerem 
Momentum rotieren. Nicht auf volle Rückkehr warten - agil handeln!

MOMENTUM-ERSCHÖPFUNG ERKENNEN:
1. Sentiment-Rückgang: Position hat >15% Gewinn, aber aktuelles Sentiment 
   ist schwächer als beim Entry (z.B. von 80 auf 50 gefallen)
2. Volumen-Abnahme: Diskussionen auf X/Reddit nehmen ab trotz Gewinnposition
3. Narrative-Shift: Aufmerksamkeit wandert zu anderen Coins
4. Seitwärtsbewegung: Kurs konsolidiert seit mehreren Zyklen trotz Gewinn

PROAKTIVE REDUCE-REGELN (Gewinne mitnehmen, Kapital freisetzen):

+10-20% PnL + nachlassendes Momentum -> REDUCE 30-40%
   Begründung: Frühe Gewinnmitnahme bei ersten Erschöpfungszeichen

+20-40% PnL + Sentiment unter 50 -> REDUCE 50%
   Begründung: Solide Gewinne sichern, halbe Position laufen lassen

+40%+ PnL -> REDUCE 50-70% (unabhängig vom Sentiment)
   Begründung: Außergewöhnliche Gewinne realisieren, Kapital rotieren

Position im Gewinn + neue Opportunity mit +30 höherer Conviction:
   -> REDUCE 50-100% der alten Position für die neue
   Begründung: Kapital folgt dem stärksten Momentum

KAPITAL-ROTATION PRIORISIEREN:
- Wenn neue high-conviction Opportunities warten (>75 Conviction)
- Und bestehende Positionen Gewinne zeigen, aber Momentum nachlässt
- -> Aktiv REDUCE nutzen, um Kapital für neue Trades freizusetzen
- -> Nicht warten bis Positionen "fertig" sind - Momentum ist vergänglich!

ANTI-PATTERN (VERMEIDEN):
- Gewinnpositionen endlos halten in der Hoffnung auf mehr
- Erst bei Trendumkehr reagieren statt bei Momentum-Erschöpfung
- Neue Opportunities verpassen weil Kapital gebunden ist

═══════════════════════════════════════════════════════════════════
AUFGABE 3: NEUE OPPORTUNITÄTEN
═══════════════════════════════════════════════════════════════════

Verfügbare Slots für neue Positionen: {available_slots}

PORTFOLIO-LIMITS (beide werden geprüft):
1. Positions-Limit: Maximal 50 offene Positionen
2. Kapital-Limit: Maximal 90% des Kapitals deployed

Suche nach neuen Trading-Opportunitäten:
- Nur Coins mit klarem Sentiment-Signal (bullish → LONG, bearish → SHORT)
- Conviction muss > 60 sein

REPLACEMENT-REGELN (wenn Limits erreicht):
- Neue Position wird NUR eröffnet wenn Conviction mindestens +25 HÖHER als die niedrigste bestehende Position ist
- Bei Replacement: Benenne explizit welche Position ersetzt werden soll und warum
- Beispiel: Neue Opportunity mit Conviction 85 kann Position mit Conviction 60 ersetzen (85 >= 60+25)

═══════════════════════════════════════════════════════════════════
OUTPUT FORMAT (STRIKT EINHALTEN!)
═══════════════════════════════════════════════════════════════════

Antworte mit einem JSON-Objekt. Das Feld "analysis_text" enthält deine menschenlesbare Analyse.

```json
{{
  "analysis_text": "📊 **Portfolio-Update {timestamp}**\\n\\n[Hier deine ausführliche, menschenlesbare Marktanalyse und Empfehlungen. Erkläre warum du bestimmte Positionen schließen, aufstocken oder reduzieren willst. Mindestens 200 Wörter.]",
  
  "market_summary": "Kurze Zusammenfassung des Gesamtmarkts in 1-2 Sätzen",
  
  "position_decisions": [
    {{
      "symbol": "BTCUSDT",
      "action": "KEEP",
      "reason": "Starkes bullishes Sentiment auf X",
      "current_sentiment": 65,
      "scale_percent": 0
    }},
    {{
      "symbol": "ETHUSDT",
      "action": "EXTEND",
      "reason": "Momentum verstärkt sich, Position aufstocken",
      "current_sentiment": 75,
      "scale_percent": 50
    }},
    {{
      "symbol": "SOLUSDT",
      "action": "REDUCE",
      "reason": "+35% Gewinn, Sentiment von 75 auf 45 gefallen - Kapital für AVAXUSDT freisetzen (Conv. 82)",
      "current_sentiment": 45,
      "scale_percent": 60
    }}
  ],
  
  "new_opportunities": [
    {{
      "symbol": "AVAXUSDT",
      "direction": "LONG",
      "conviction": 82,
      "leverage": 5,
      "sentiment_score": 72,
      "narrative_strength": 85,
      "reason": "Breaking: Avalanche Update, starke Whale-Akkumulation",
      "key_signals": ["@whale_alert: Large buy", "Avalanche Foundation announcement"]
    }},
    {{
      "symbol": "DOGEUSDT",
      "direction": "SHORT",
      "conviction": 72,
      "leverage": 4,
      "sentiment_score": -55,
      "narrative_strength": 70,
      "reason": "Pump erschöpft nach 3 Tagen Rally, Whale-Verkäufe zu Exchanges, bearishes Sentiment",
      "key_signals": ["Large DOGE transfer to Binance", "Meme fatigue auf X", "RSI überkauft"]
    }}
  ],
  
  "coins_analyzed": 47,
  "coins_skipped": 53
}}
```

WICHTIG:
- "analysis_text" MUSS eine ausführliche, menschenlesbare Analyse sein (für das Logbook)
- Alle Preise und Symbole müssen Binance Futures Format haben (z.B. BTCUSDT)
- Leverage zwischen 1-10 basierend auf Conviction
- scale_percent nur bei EXTEND/REDUCE verwenden (10-100)
- Bei KEEP und CLOSE ist scale_percent immer 0
- Übersprungene Coins haben keine ausreichenden 10-Minuten-Daten

═══════════════════════════════════════════════════════════════════
JETZT ANALYSIEREN - NUR JSON AUSGEBEN
═══════════════════════════════════════════════════════════════════"""

    async def analyze(
        self,
        positions_context: str,
        available_slots: int,
        deployment_info: str = "",
    ) -> AnalysisResult:
        """
        Run comprehensive Grok analysis.
        
        Args:
            positions_context: Formatted string of current positions
            available_slots: Number of slots available for new positions
            deployment_info: Deployment status message (below minimum warning)
            
        Returns:
            AnalysisResult with decisions and human-readable text
        """
        prompt = self._build_prompt(positions_context, available_slots, deployment_info)
        
        system_prompt = """You are a professional crypto portfolio manager with real-time access to market data.

CRITICAL: You MUST use your search tools (x_keyword_search, x_semantic_search, web_search) to gather CURRENT data from the last 10 minutes.

Your internal knowledge is outdated. Only real-time search results matter.

Always output valid JSON as specified in the prompt."""

        # Build full prompt for debugging (system + user)
        full_prompt = f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{prompt}"
        
        if not self.api_key:
            logger.error("No XAI_API_KEY - returning empty analysis")
            return self._empty_result("API key not configured", raw_prompt=full_prompt)

        try:
            client = await self._get_client()
            
            request_body = {
                "model": self.MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,  # Lower for more consistent output
                "max_tokens": 8000,  # Large response for comprehensive analysis
                "search_parameters": {
                    "mode": "auto",
                    "return_citations": True,
                }
            }
            
            logger.info("Calling Grok for portfolio analysis...")
            
            response = await client.post(
                f"{self.XAI_BASE_URL}/chat/completions",
                json=request_body
            )
            
            if response.status_code != 200:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return self._empty_result(f"API error: {response.status_code}", raw_prompt=full_prompt, raw_response=response.text)
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)
            
            logger.info(f"Grok response received ({tokens_used} tokens)")
            
            return self._parse_response(content, tokens_used, raw_prompt=full_prompt, raw_response=content)
            
        except Exception as e:
            logger.error(f"Grok analysis failed: {e}", exc_info=True)
            return self._empty_result(f"Analysis failed: {str(e)}", raw_prompt=full_prompt)
    
    def _parse_response(self, content: str, tokens_used: int, raw_prompt: str = "", raw_response: str = "") -> AnalysisResult:
        """Parse Grok's JSON response into AnalysisResult."""
        try:
            # Extract JSON from markdown code block if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            # Find JSON object
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                content = content[json_start:json_end]
            
            data = json.loads(content)
            
            # Parse position decisions
            position_decisions = []
            for pd in data.get("position_decisions", []):
                action = pd.get("action", "KEEP").upper()
                # Validate action
                if action not in ["KEEP", "CLOSE", "EXTEND", "REDUCE"]:
                    action = "KEEP"
                
                # Get scale_percent for EXTEND/REDUCE
                scale_percent = 0
                if action in ["EXTEND", "REDUCE"]:
                    scale_percent = int(pd.get("scale_percent", 50))
                    # Clamp to valid range
                    scale_percent = max(10, min(100, scale_percent))
                
                position_decisions.append(PositionDecision(
                    symbol=pd.get("symbol", ""),
                    action=action,
                    reason=pd.get("reason", ""),
                    current_sentiment=int(pd.get("current_sentiment", 0)),
                    scale_percent=scale_percent,
                ))
            
            # Parse new opportunities
            new_opportunities = []
            for opp in data.get("new_opportunities", []):
                direction = opp.get("direction", "").upper()
                if direction not in ["LONG", "SHORT"]:
                    continue  # Skip invalid directions
                
                conviction = int(opp.get("conviction", 0))
                if conviction < 60:
                    continue  # Skip low conviction
                
                new_opportunities.append(NewOpportunity(
                    symbol=opp.get("symbol", ""),
                    direction=direction,
                    conviction=conviction,
                    leverage=min(10, max(1, int(opp.get("leverage", 3)))),
                    sentiment_score=int(opp.get("sentiment_score", 0)),
                    narrative_strength=int(opp.get("narrative_strength", 0)),
                    reason=opp.get("reason", ""),
                    key_signals=opp.get("key_signals", [])[:5],
                ))
            
            # Sort opportunities by conviction (highest first)
            new_opportunities.sort(key=lambda x: x.conviction, reverse=True)
            
            return AnalysisResult(
                analysis_text=data.get("analysis_text", "No analysis text provided"),
                market_summary=data.get("market_summary", ""),
                position_decisions=position_decisions,
                new_opportunities=new_opportunities,
                coins_analyzed=int(data.get("coins_analyzed", 0)),
                coins_skipped=int(data.get("coins_skipped", 0)),
                tokens_used=tokens_used,
                raw_prompt=raw_prompt,
                raw_response=raw_response,
            )
            
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse Grok response: {e}")
            logger.debug(f"Raw content: {content[:1000]}")
            return self._empty_result(f"Parse error: {str(e)}", raw_prompt=raw_prompt, raw_response=raw_response)
    
    def _empty_result(self, reason: str, raw_prompt: str = "", raw_response: str = "") -> AnalysisResult:
        """Return an empty result when analysis fails."""
        return AnalysisResult(
            analysis_text=f"⚠️ Analysis could not be completed: {reason}",
            market_summary="Analysis unavailable",
            position_decisions=[],
            new_opportunities=[],
            coins_analyzed=0,
            coins_skipped=0,
            raw_prompt=raw_prompt,
            raw_response=raw_response,
        )
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

