"""
Predictor - Asks Grok for LONG/SHORT predictions with robust sentiment analysis

Uses Grok's real-time tools to analyze:
- Twitter/X sentiment
- News & media coverage
- Technical indicators
- Reddit & community sentiment
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SentimentBreakdown:
    """Breakdown of sentiment from different sources."""
    twitter: int = 0  # -100 to +100
    news: int = 0
    technical: int = 0
    reddit: int = 0
    
    def to_dict(self) -> dict:
        return {
            "twitter": self.twitter,
            "news": self.news,
            "technical": self.technical,
            "reddit": self.reddit,
        }


@dataclass
class Prediction:
    """A single coin prediction with extended sentiment data."""
    coin: str
    direction: str  # "LONG", "SHORT", or "NEUTRAL"
    conviction: int  # 30-95
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Extended fields from new prompt
    sentiment_breakdown: Optional[SentimentBreakdown] = None
    key_signals: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    data_quality: str = "MEDIUM"  # HIGH, MEDIUM, LOW
    
    @property
    def leverage(self) -> float:
        """
        Calculate leverage from conviction.
        
        - NEUTRAL: 1.0x
        - conviction 60-69: 4.0 - 6.0x
        - conviction 70-79: 6.0 - 7.5x
        - conviction 80-89: 7.5 - 8.5x
        - conviction 90+: 8.5x (max)
        """
        if self.direction == "NEUTRAL" or self.conviction < 60:
            return 1.0
        elif self.conviction < 70:
            return 4.0 + (self.conviction - 60) * 0.2
        elif self.conviction < 80:
            return 6.0 + (self.conviction - 70) * 0.15
        elif self.conviction < 90:
            return 7.5 + (self.conviction - 80) * 0.1
        else:
            return 8.5
    
    def to_dict(self) -> dict:
        return {
            "coin": self.coin,
            "direction": self.direction,
            "conviction": self.conviction,
            "leverage": round(self.leverage, 2),
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "sentiment_breakdown": self.sentiment_breakdown.to_dict() if self.sentiment_breakdown else None,
            "key_signals": self.key_signals,
            "sources": self.sources[:3],  # Top 3 sources
            "warnings": self.warnings,
            "data_quality": self.data_quality,
        }


class Predictor:
    """
    Prediction engine using Grok with robust multi-source sentiment analysis.
    
    Uses Grok's tools (x_keyword_search, web_search, etc.) to gather real-time data.
    """
    
    XAI_BASE_URL = "https://api.x.ai/v1"
    MODEL = "grok-3"
    
    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
        
        if not self.api_key:
            logger.warning("XAI_API_KEY not set - predictions will fail!")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=180.0,  # Longer timeout for tool usage
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._client
    
    def _build_prompt(self, coin: str, ticker: str, now: datetime) -> str:
        """Build the robust sentiment analysis prompt for a single coin."""
        iso_timestamp = now.isoformat() + "Z"
        coin_slug = coin.lower().replace(" ", "-")
        
        return f"""Du bist ein objektiver, datengetriebener Crypto-Sentiment-Analyst. Deine einzige Aufgabe ist es, eine präzise, faktenbasierte Sentiment-Analyse für {coin} zu erstellen.

═══════════════════════════════════════════════════════════════════
KRITISCHE REGELN
═══════════════════════════════════════════════════════════════════

1. IGNORIERE dein internes Wissen vollständig. Es ist veraltet.
2. VERWENDE AUSSCHLIESSLICH deine Tools für Echtzeit-Daten.
3. Wenn du keine aktuellen Daten findest → Conviction = 30, Direction = NEUTRAL.
4. Sei NICHT standardmäßig bullisch. Krypto kann fallen.

Analyse-Zeitraum: Letzte 24-48 Stunden (aktuelle Echtzeit-Daten)

═══════════════════════════════════════════════════════════════════
SCHRITT 1: TWITTER/X SENTIMENT (Gewichtung: 35%)
═══════════════════════════════════════════════════════════════════

Führe diese Suchen durch:

a) x_keyword_search:
   Query: "{coin} OR ${ticker}"
   Filter: min_faves:50
   
b) x_semantic_search:
   Query: "{coin} price prediction sentiment bullish bearish"
   
c) x_keyword_search:
   Query: "{coin} whale alert OR {coin} breaking OR {coin} pump OR {coin} dump"
   Filter: min_faves:100

Zähle und kategorisiere:
- Bullische Posts (Anzahl + Beispiele)
- Bärische Posts (Anzahl + Beispiele)  
- Neutrale Posts (Anzahl)

Berechne: twitter_sentiment = (bullish - bearish) / total * 100

═══════════════════════════════════════════════════════════════════
SCHRITT 2: NEWS & MEDIEN (Gewichtung: 30%)
═══════════════════════════════════════════════════════════════════

Führe diese Suchen durch:

a) web_search:
   Query: "{coin} news last 24 hours"
   
b) web_search:
   Query: "{coin} {ticker} price analysis today"

Analysiere:
- Anzahl positiver Headlines
- Anzahl negativer Headlines
- Wichtige Ereignisse (Partnerships, Hacks, Listings, Regulatory News)

Berechne: news_sentiment = (positive - negative) / total * 100

═══════════════════════════════════════════════════════════════════
SCHRITT 3: TECHNISCHE INDIKATOREN & MARKTDATEN (Gewichtung: 20%)
═══════════════════════════════════════════════════════════════════

a) web_search:
   Query: "{coin} technical analysis RSI MACD today"

b) web_search:
   Query: "{coin} funding rate open interest"

Extrahiere:
- 24h Preisänderung (%)
- Volumen-Trend (steigend/fallend)
- Funding Rate (positiv = überkauft, negativ = überverkauft)
- RSI wenn verfügbar (<30 überverkauft, >70 überkauft)

Berechne: technical_sentiment basierend auf Indikatoren

═══════════════════════════════════════════════════════════════════
SCHRITT 4: REDDIT & COMMUNITY (Gewichtung: 15%)
═══════════════════════════════════════════════════════════════════

a) web_search:
   Query: "site:reddit.com {coin} last 24 hours"

b) web_search:
   Query: "{coin} reddit sentiment community"

Analysiere:
- Stimmung in relevanten Subreddits
- Fear vs. Greed Tendenz

Berechne: reddit_sentiment

═══════════════════════════════════════════════════════════════════
SCHRITT 5: FINALE BERECHNUNG
═══════════════════════════════════════════════════════════════════

CONVICTION FORMEL:
conviction_raw = (twitter_sentiment * 0.35) + (news_sentiment * 0.30) + (technical_sentiment * 0.20) + (reddit_sentiment * 0.15)

DATENQUALITÄTS-ABZUG:
- Weniger als 10 Twitter-Posts gefunden: -15
- Weniger als 3 News-Artikel gefunden: -10
- Keine technischen Daten: -10
- Widersprüchliche Signale: -20

conviction_final = max(30, min(95, 50 + conviction_raw - abzüge))

DIRECTION BESTIMMUNG:
- conviction_final >= 60 UND sentiment überwiegend positiv → LONG
- conviction_final >= 60 UND sentiment überwiegend negativ → SHORT
- conviction_final < 60 ODER gemischte Signale → NEUTRAL

LEVERAGE BERECHNUNG:
- NEUTRAL: leverage = 1.0
- conviction 60-69: leverage = 4.0 + (conviction - 60) * 0.2
- conviction 70-79: leverage = 6.0 + (conviction - 70) * 0.15
- conviction 80-89: leverage = 7.5 + (conviction - 80) * 0.1
- conviction 90+: leverage = 8.5 (Maximum)

═══════════════════════════════════════════════════════════════════
OUTPUT FORMAT (STRIKT EINHALTEN)
═══════════════════════════════════════════════════════════════════

Antworte NUR mit diesem JSON. Kein Text davor oder danach:

{{
  "coin": "{coin}",
  "ticker": "{ticker}",
  "timestamp": "{iso_timestamp}",
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "conviction": <30-95>,
  "leverage": <1.0-8.5>,
  "reason": "<1-2 Sätze: Hauptgrund für die Entscheidung>",
  "sentiment_breakdown": {{
    "twitter": <-100 bis +100>,
    "news": <-100 bis +100>,
    "technical": <-100 bis +100>,
    "reddit": <-100 bis +100>
  }},
  "key_signals": [
    "<Signal 1>",
    "<Signal 2>",
    "<Signal 3>"
  ],
  "sources": [
    "<URL oder @username 1>",
    "<URL oder @username 2>",
    "<URL oder @username 3>"
  ],
  "warnings": [
    "<Warnung falls Datenqualität niedrig oder Risiken erkannt>"
  ],
  "data_quality": "HIGH" | "MEDIUM" | "LOW"
}}

═══════════════════════════════════════════════════════════════════
JETZT ANALYSIERE: {coin} ({ticker})
═══════════════════════════════════════════════════════════════════"""

    async def predict_all(self, coins: List[str]) -> List[Prediction]:
        """
        Get predictions for all coins by calling Grok for each coin individually.
        
        Args:
            coins: List of coin symbols (e.g., ["BTC", "ETH", "SOL"])
            
        Returns:
            List of Prediction objects, one per coin
        """
        if not self.api_key:
            logger.error("No API key - returning neutral predictions")
            return self._fallback_predictions(coins)
        
        predictions = []
        now = datetime.utcnow()
        
        # Process coins in parallel batches
        for coin in coins:
            try:
                prediction = await self._predict_single(coin, now)
                predictions.append(prediction)
            except Exception as e:
                logger.error(f"Failed to predict {coin}: {e}")
                predictions.append(self._fallback_prediction(coin))
        
        logger.info(f"Got {len(predictions)} predictions from Grok")
        return predictions
    
    async def _predict_single(self, coin: str, now: datetime) -> Prediction:
        """Get prediction for a single coin."""
        ticker = coin.upper()
        prompt = self._build_prompt(coin, ticker, now)
        
        system_prompt = """You are a professional crypto sentiment analyst with access to real-time data tools.

IMPORTANT: You MUST use your tools (x_keyword_search, x_semantic_search, web_search) to gather current data.
Do NOT rely on your training data - it is outdated.

Always output valid JSON as specified in the prompt."""

        try:
            client = await self._get_client()
            
            # Try to enable live search via xAI's search parameter
            request_body = {
                "model": self.MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 1500,
                "search_parameters": {
                    "mode": "auto",  # Enable automatic search when needed
                    "return_citations": True,
                }
            }
            
            response = await client.post(
                f"{self.XAI_BASE_URL}/chat/completions",
                json=request_body
            )
            
            if response.status_code != 200:
                logger.error(f"Grok API error for {coin}: {response.status_code} - {response.text}")
                return self._fallback_prediction(coin)
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            return self._parse_single_prediction(content, coin)
            
        except Exception as e:
            logger.error(f"Prediction error for {coin}: {e}", exc_info=True)
            return self._fallback_prediction(coin)
    
    def _parse_single_prediction(self, content: str, coin: str) -> Prediction:
        """Parse a single prediction from Grok response."""
        try:
            # Try to extract JSON from markdown code block if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            # Find JSON object in content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                content = content[json_start:json_end]
            
            pred = json.loads(content)
            
            # Extract direction
            direction = pred.get("direction", "NEUTRAL").upper()
            if direction not in ["LONG", "SHORT", "NEUTRAL"]:
                direction = "NEUTRAL"
            
            # Check if we should reverse signals (contrarian mode)
            reverse_signals = os.getenv("REVERSE_SIGNALS", "").lower() == "true"
            if reverse_signals and direction != "NEUTRAL":
                direction = "SHORT" if direction == "LONG" else "LONG"
            
            # Extract conviction (clamp to 30-95)
            conviction = int(pred.get("conviction", 50))
            conviction = max(30, min(95, conviction))
            
            # Extract sentiment breakdown
            sentiment_data = pred.get("sentiment_breakdown", {})
            sentiment_breakdown = SentimentBreakdown(
                twitter=int(sentiment_data.get("twitter", 0)),
                news=int(sentiment_data.get("news", 0)),
                technical=int(sentiment_data.get("technical", 0)),
                reddit=int(sentiment_data.get("reddit", 0)),
            )
            
            # Log data quality
            data_quality = pred.get("data_quality", "MEDIUM")
            if data_quality == "LOW":
                logger.warning(f"{coin}: Low data quality - {pred.get('warnings', [])}")
            
            return Prediction(
                coin=coin.upper(),
                direction=direction,
                conviction=conviction,
                reason=pred.get("reason", "")[:200],
                sentiment_breakdown=sentiment_breakdown,
                key_signals=pred.get("key_signals", [])[:5],
                sources=pred.get("sources", [])[:5],
                warnings=pred.get("warnings", []),
                data_quality=data_quality,
            )
            
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse prediction for {coin}: {e}")
            logger.debug(f"Raw content: {content[:500]}")
            return self._fallback_prediction(coin)
    
    def _fallback_prediction(self, coin: str) -> Prediction:
        """Return a neutral prediction for a single coin."""
        return Prediction(
            coin=coin.upper(),
            direction="NEUTRAL",
            conviction=30,
            reason="Fallback - insufficient data",
            data_quality="LOW",
            warnings=["Using fallback prediction due to API error"],
        )
    
    def _fallback_predictions(self, coins: List[str]) -> List[Prediction]:
        """Return neutral predictions when Grok fails."""
        logger.warning("Using fallback neutral predictions")
        return [self._fallback_prediction(coin) for coin in coins]
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
