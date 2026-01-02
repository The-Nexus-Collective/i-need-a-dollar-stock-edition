# Production Trading Platform

Enterprise-grade autonomous trading system with AI-powered sentiment analysis, real-time risk management, complete audit trails, and institutional-grade infrastructure.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Next.js 14 Dashboard                             │   │
│  │  • Command Center (equity, positions, signals)                       │   │
│  │  • Risk Console (VaR, limits, circuit breakers)                      │   │
│  │  • Audit Trail (hash-chain verified logs)                            │   │
│  │  • Real-time WebSocket updates                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      FastAPI + WebSocket                             │   │
│  │  • JWT Authentication                                                │   │
│  │  • REST API (/api/*)                                                 │   │
│  │  • WebSocket (/ws) for real-time events                              │   │
│  │  • OpenAPI documentation                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EVENT BUS (Redis Streams)                          │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │  signals  │  │   risk    │  │  orders   │  │ positions │              │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘              │
│         ▲             ▲              ▲              ▲                      │
│         │             │              │              │                      │
│         ▼             ▼              ▼              ▼                      │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │  Signal   │  │   Risk    │  │   Order   │  │ Portfolio │              │
│  │  Engine   │  │  Manager  │  │ Executor  │  │  Manager  │              │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │   PostgreSQL +    │  │      Redis       │  │   Audit Log      │         │
│  │   TimescaleDB     │  │   (Event Bus)    │  │  (Hash-Chained)  │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SERVICES                                  │
│  ┌──────────────────┐                      ┌──────────────────┐            │
│  │     Grok AI      │                      │  Binance API     │            │
│  │  (Sentiment)     │                      │ (Market Data)    │            │
│  └──────────────────┘                      └──────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- xAI API key from [x.ai/api](https://x.ai/api)

### 1. Clone and Configure

```bash
git clone <repository-url>
cd trading-platform

# Copy and edit environment file
cp env.example .env

# Add your xAI API key
nano .env
```

### 2. Launch the Platform

```bash
# Start all services
docker compose up --build

# Or run in background
docker compose up -d --build
```

### 3. Access the Dashboard

- **Streamlit Dashboard**: http://localhost:8501 (recommended)
- **Next.js Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Grafana** (optional): http://localhost:3001

## Services

| Service | Port | Description |
|---------|------|-------------|
| **Streamlit Dashboard** | **8501** | **Real-time trading dashboard** |
| Trading Bot | - | Main strategy orchestrator |
| Frontend (Next.js) | 3000 | Alternative dashboard |
| API Gateway (FastAPI) | 8000 | REST API + WebSocket |
| PostgreSQL + TimescaleDB | 5432 | Primary database |
| Redis | 6379 | Event bus |
| Prometheus | 9090 | Metrics (optional) |
| Grafana | 3001 | Dashboards (optional) |

## Trading Strategy

The bot implements a proven sentiment-driven strategy:

### Core Logic
1. **Every hour**: Query Grok AI for sentiment (-100 to +100) and narrative strength (0-100)
2. **Calculate Score**: `Score = sentiment × (narrative / 100)`
3. **Select best coin**: Highest |Score| that passes all filters
4. **Execute**: Long if Score > 0, Short if Score < 0

### Filters
- **Score Threshold**: Only trade if |Score| >= 65
- **Volume Filter**: Only trade if 1h volume >= 80% of 24h average

### Risk Management
- **Position Size**: `2% equity / (1.5 × ATR)`
- **Stop Loss**: 1.5 × ATR
- **Take Profit**: 4 × ATR
- **Daily Flatten**: All positions closed at 23:55 CET

## Core Components

### Signal Engine
- Queries Grok AI for sentiment analysis on top 10 coins
- Calculates combined score: `sentiment × (narrative / 100)`
- Generates trading signals with confidence scores
- Runs hourly (configurable)

### Risk Manager
- **Position Limits**: 10% per asset, 30% altcoins, 80% total deployed
- **Drawdown Circuit Breakers**:
  - Level 1 (5%): Reduce position sizes by 50%
  - Level 2 (10%): Close all positions, switch to paper
  - Level 3 (15%): Full system halt
- **VaR Monitoring**: 95% VaR calculated in real-time
- All trades require risk approval before execution

### Order Executor
- Paper mode: Simulated execution with market data from Binance
- Live mode: Real execution via Binance Futures (requires API keys)
- Automatic stop-loss and take-profit monitoring
- Position tracking with P&L calculations

### Audit System
- Every decision logged with microsecond precision
- Cryptographic hash chain for tamper detection
- Before/after state capture
- AI reasoning logging
- Searchable audit trail in dashboard

## Event Types

```python
# Signal Events
SIGNAL_GENERATED      # New AI signal
RISK_CHECK_REQUESTED  # Signal awaiting approval

# Risk Events
RISK_APPROVED         # Trade approved
RISK_REJECTED         # Trade blocked
CIRCUIT_BREAKER_TRIGGERED  # Emergency stop

# Order Events
ORDER_SUBMITTED       # Order sent
ORDER_FILLED          # Execution confirmed

# Position Events
POSITION_OPENED       # New position
POSITION_UPDATED      # P&L update
POSITION_CLOSED       # Position closed
```

## API Endpoints

### Authentication
```bash
# Get token
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

### Portfolio
```bash
# Get current portfolio
curl http://localhost:8000/api/portfolio

# Get equity history
curl http://localhost:8000/api/portfolio/history?limit=500
```

### Positions
```bash
# Get open positions
curl http://localhost:8000/api/positions?status=open
```

### Signals
```bash
# Get latest signals
curl http://localhost:8000/api/signals/latest
```

### Audit
```bash
# Get audit log
curl http://localhost:8000/api/audit?limit=100

# Verify chain integrity
curl http://localhost:8000/api/audit/verify
```

## Strategy Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SCORE_THRESHOLD` | 65 | Minimum |Score| to enter trade |
| `VOLUME_FILTER_RATIO` | 0.80 | 1h vol must be >= 80% of 24h avg |
| `RISK_PER_TRADE` | 0.02 | Risk 2% of equity per trade |
| `STOP_LOSS_ATR_MULT` | 1.5 | Stop loss as ATR multiple |
| `TAKE_PROFIT_ATR_MULT` | 4.0 | Take profit as ATR multiple |
| `INITIAL_EQUITY` | 10000 | Starting paper equity in USDT |
| `FLATTEN_TIME_CET` | 23:55 | Daily flatten time in CET |

## Risk Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `POSITION_LIMIT_PER_ASSET` | 10% | Max in single asset |
| `POSITION_LIMIT_ALTCOINS` | 30% | Max in non-BTC/ETH |
| `MAX_DEPLOYED` | 80% | Max portfolio deployed |
| `DRAWDOWN_LEVEL_1` | 5% | Circuit breaker level 1 |
| `DRAWDOWN_LEVEL_2` | 10% | Circuit breaker level 2 |
| `DRAWDOWN_LEVEL_3` | 15% | Circuit breaker level 3 |

## Development

### Local Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start services
docker compose up postgres redis -d

# Run gateway
uvicorn gateway.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
cd backend
pytest tests/ -v
```

### Database Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Monitoring

### Enable Monitoring Stack

```bash
docker compose --profile monitoring up -d
```

Access Grafana at http://localhost:3001 (admin/admin)

### Key Metrics

- Portfolio equity over time
- Position P&L
- Signal accuracy
- Risk limit utilization
- System latency

## Security Considerations

1. **API Keys**: Never commit real keys to version control
2. **JWT Secret**: Generate a strong random secret for production
3. **Database**: Use strong passwords and network isolation
4. **Paper Mode**: Always test thoroughly before live trading
5. **Circuit Breakers**: Ensure they're properly configured

## Live Trading Warning

⚠️ **DANGER**: Live trading with real money carries significant risk.

Before enabling live mode:
1. Test extensively in paper mode
2. Start with minimal capital
3. Monitor continuously
4. Have manual override procedures
5. Understand all risks involved

```bash
# To enable live trading (NOT RECOMMENDED without extensive testing)
MODE=live
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
```

## License

MIT License - See LICENSE file for details.

## Disclaimer

This software is for educational and research purposes only. Trading cryptocurrencies involves significant risk of loss. Past performance does not guarantee future results. The authors are not responsible for any financial losses incurred through the use of this software.