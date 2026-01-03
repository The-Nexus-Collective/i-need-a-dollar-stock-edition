# I Need A Dollar 💸

**Fully Autonomous Agentic Crypto Trading System (2026)**

A state-of-the-art trading platform featuring a multi-agent architecture powered by Grok AI. The system thinks, learns, experiments, and adapts continuously—operating like a top-tier quant trader with infinite curiosity while respecting strict risk controls.

## 🧠 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR (Central Brain)                     │
│                    Coordinates 15-minute trading cycles                  │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   Discovery   │           │   Validation  │           │   Sentiment   │
│     Agent     │           │     Agent     │           │     Agent     │
│               │           │               │           │               │
│ CoinGecko API │           │ Volume checks │           │ Grok-powered  │
│ X/Twitter     │           │ Exchange list │           │ Batch analysis│
│ Hype scanning │           │ Age/Liquidity │           │ Regime detect │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   Strategy    │           │   Execution   │           │    Learner    │
│   Ensemble    │           │     Agent     │           │     Agent     │
│               │           │               │           │               │
│ 6 strategies  │           │ Paper/Live    │           │ Post-trade    │
│ Meta-learning │           │ TWAP/Market   │           │ Reflection    │
│ Weight adjust │           │ Risk checks   │           │ Memory store  │
└───────────────┘           └───────────────┘           └───────────────┘
                                    │
                                    ▼
                         ┌───────────────────┐
                         │   Agent Logbook   │
                         │                   │
                         │ Full transparency │
                         │ Semantic search   │
                         │ pgvector storage  │
                         └───────────────────┘
```

## 🚀 Features

### Multi-Agent System
- **Discovery Agent**: Continuously discovers new opportunities from CoinGecko and X/Twitter
- **Validation Agent**: Validates assets meet minimum requirements ($10M volume, 7+ days old)
- **Sentiment Agent**: Batch Grok analysis for sentiment scoring and regime detection
- **Strategy Ensemble**: 6 sub-strategies with meta-learning weight adjustment
- **Execution Agent**: Paper trading with realistic fees and slippage simulation
- **Learner Agent**: Post-trade reflection and memory-based learning

### Dynamic Universe
- No fixed coin list—the system discovers and validates opportunities autonomously
- X/Twitter scanning for emerging coins and hype events
- Narrative detection (AI, DeFi, meme coins, L2, RWA, gaming)
- Automatic expiration of stale assets

### Self-Improvement
- Short/medium/long-term memory via pgvector
- Semantic search for relevant past experiences
- Strategy variant generation from trade reflections
- Regime-aware weight adjustment

### Risk Controls
- 12% max per existing coin, 8% max per new coin
- 35% max in new/unproven coins
- 5% daily loss kill switch
- 23:55 CET daily flatten
- Grok-powered trade approval gate

## 📁 Project Structure

```
backend/
├── agents/                 # Multi-agent architecture
│   ├── base.py            # BaseAgent with think/act/log lifecycle
│   ├── logbook.py         # Central audit trail with pgvector
│   ├── orchestrator.py    # Central brain coordinating all agents
│   ├── discovery.py       # CoinGecko + X discovery
│   ├── validation.py      # Asset validation pipeline
│   ├── sentiment.py       # Grok-powered sentiment analysis
│   ├── strategy_ensemble.py # 6 strategies + meta-learner
│   ├── execution.py       # Trade execution (paper/live)
│   └── learner.py         # Post-trade reflection + memory
├── core/                   # Core trading logic
├── gateway/               # FastAPI + WebSocket API
├── integrations/          # External API clients
│   ├── coingecko.py       # CoinGecko market data
│   └── x_client.py        # X/Twitter hype detection
├── migrations/            # PostgreSQL + pgvector migrations
├── models/                # SQLAlchemy models
└── main.py               # Main entry point

frontend/
├── app/
│   ├── page.tsx          # Dashboard
│   ├── agents/           # Agent Logbook viewer
│   ├── universe/         # Dynamic universe explorer
│   ├── strategies/       # Strategy ensemble viewer
│   ├── positions/        # Open positions
│   ├── history/          # Trade history
│   └── risk/             # Risk metrics
└── components/           # Reusable UI components
```

## 🛠 Setup

### Prerequisites
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### Environment Variables

```bash
# Copy example and fill in your keys
cp env.example .env

# Required API Keys:
# - XAI_API_KEY (Grok): https://console.x.ai
# - X_BEARER_TOKEN: https://developer.twitter.com
# - OPENAI_API_KEY (optional, for embeddings): https://platform.openai.com
```

### Running Locally

```bash
# Start all services
docker-compose up -d

# Or use the helper script
./scripts/start-local.sh
```

### Services
- **Backend API**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **PostgreSQL**: localhost:5432 (with pgvector)
- **Prometheus**: http://localhost:9090

## 🔄 Trading Cycle (Every 15 Minutes)

1. **Discovery**: Pull top 200 coins from CoinGecko, scan X for hype
2. **Validation**: Filter to tradable assets (volume, exchange, age)
3. **Sentiment**: Batch Grok analysis for all validated coins
4. **Strategy**: Generate proposals from 6 strategies, apply weights
5. **Approval**: Grok final decision on proposed trades
6. **Execution**: Execute approved trades with paper/live mode
7. **Learning**: Reflect on closed trades, store memories

## 📊 Strategies

| Strategy | Description | Best Regime |
|----------|-------------|-------------|
| **Momentum** | Ride strong trends with high conviction | Low/Normal Vol |
| **Mean Reversion** | Fade extreme readings | Normal Vol |
| **Hype Following** | Trade high X engagement coins | Euphoria |
| **Contrarian** | Go against extreme crowd sentiment | Panic |
| **Volatility Expansion** | Catch breakouts from low vol | Low Vol |
| **Narrative Driven** | Trade dominant themes (AI, DeFi, etc) | Any |

## 🔒 Risk Limits

- **Per Coin**: 12% max (8% for new coins)
- **New Coin Bucket**: 35% max in unproven assets
- **Daily Loss**: 5% kill switch
- **Total Deployment**: 90% max
- **Leverage**: 3-6x adaptive

## 📝 Agent Logbook

Every agent action is logged with full transparency:
- **Reasoning**: Why did the agent do this?
- **Decision**: What was decided?
- **Confidence**: How certain was the agent?
- **Duration**: How long did it take?
- **Tokens**: How many Grok tokens were used?

Access the logbook at `/agents` in the frontend.

## 🧪 Development

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm run dev
```

## 📜 License

MIT License - Use at your own risk. This is experimental software for paper trading.

---

Built with ❤️ using Grok AI, FastAPI, Next.js, and PostgreSQL/pgvector
