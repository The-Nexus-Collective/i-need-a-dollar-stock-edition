# I Need A Dollar Stock Edition

A production-grade autonomous stock trading platform with AI-powered sentiment analysis, built with Spring Boot and Next.js.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
│                   (Next.js + React + Tailwind)                       │
│                        Port 3100                                     │
├─────────────────────────────────────────────────────────────────────┤
│                              ↕                                       │
│                     REST API + WebSocket                             │
├─────────────────────────────────────────────────────────────────────┤
│                           BACKEND                                    │
│                    (Spring Boot + Liquibase)                         │
│                        Port 8081                                     │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐          │
│  │ Controllers │   Services  │ Repositories│ WebSocket   │          │
│  └─────────────┴─────────────┴─────────────┴─────────────┘          │
│  ┌─────────────┬─────────────┐                                       │
│  │Yahoo Finance│   Grok AI   │  (External Integrations)             │
│  └─────────────┴─────────────┘                                       │
├─────────────────────────────────────────────────────────────────────┤
│                           DATABASE                                   │
│                      (PostgreSQL + Liquibase)                        │
│                        Port 5433                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

- **Backend**: Java 21, Spring Boot 3.2, Spring Data JPA, Spring WebSocket
- **Database**: PostgreSQL 15, Liquibase for migrations
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS
- **External APIs**: Yahoo Finance (price data), Grok xAI (trading decisions)
- **Broker**: CapTrader/IBKR (future integration, currently paper trading)

## Stock Universe

The platform focuses on highly liquid stocks in two sectors:

### Tech Stocks
AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, ADBE, CRM, INTC, CSCO, IBM, ORCL, SAP, ASML, TXN, QCOM, AMD, AVGO, MU

### Defense Stocks
LMT, RTX, BA, GD, NOC, LHX, HII, TDY, TXT, KBR, FLIR, OSK, VEC, AJRD, HEI, CW, ESMC, SRDX, IRDM, MAXR

## Quick Start

### Prerequisites

- Java 21+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL (or use Docker)

### Local Development

```bash
# Start all services
./scripts/start-local.sh
```

Or manually:

```bash
# Start database
docker-compose up -d postgres

# Start backend (in one terminal)
cd backend
./gradlew bootRun

# Start frontend (in another terminal)
cd frontend
npm install
PORT=3100 npm run dev
```

### Access Points

- **Frontend**: http://localhost:3100
- **Backend API**: http://localhost:8081
- **API Docs (Swagger)**: http://localhost:8081/swagger-ui.html
- **Health Check**: http://localhost:8081/health

## API Endpoints

### Portfolio

- `GET /api/portfolio` - Get current portfolio state
- `GET /api/portfolio-manager/status` - Get portfolio manager status
- `POST /api/portfolio-manager/cycle` - Trigger trading cycle
- `DELETE /api/paper-trades/reset` - Reset paper trading

### Positions

- `GET /api/positions` - Get all positions (query: status=open|closed)
- `GET /api/positions/open` - Get open positions
- `GET /api/positions/closed` - Get closed positions
- `GET /api/positions/{id}` - Get position by ID

### Trades

- `GET /api/trades` - Get recent trades
- `GET /api/trades/today` - Get today's trades
- `GET /api/trades/stats` - Get trading statistics

### Signals

- `GET /api/signals` - Get recent signals
- `GET /api/signals/executed` - Get executed signals

### Risk

- `GET /api/risk/events` - Get risk events
- `GET /api/risk/summary` - Get risk summary
- `GET /api/risk/status` - Get risk status

### Audit

- `GET /api/audit` - Get audit log entries

### System

- `GET /health` - Health check
- `GET /api/system/status` - System status

## WebSocket Endpoints

- `ws://localhost:8081/ws/equity` - Real-time equity streaming
- `ws://localhost:8081/ws` - General event streaming

## Environment Variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `jdbc:postgresql://localhost:5435/trading_stock` | Database connection URL |
| `DB_USERNAME` | `postgres` | Database username |
| `DB_PASSWORD` | `postgres` | Database password |
| `XAI_API_KEY` | - | Grok xAI API key |
| `MODE` | `paper` | Trading mode (paper/live) |
| `CYCLE_INTERVAL` | `600000` | Trading cycle interval (ms) |
| `STARTING_CAPITAL` | `1000000` | Starting capital (USD) |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8081` | Backend API URL |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8081/ws/equity` | WebSocket URL |

## Market Hours

The platform respects NYSE/NASDAQ trading hours:
- **Trading Hours**: 9:30 AM - 4:00 PM ET (Monday - Friday)
- **Holidays**: US stock market holidays are observed
- **Outside Hours**: The system will analyze but not trade when market is closed

## Docker Deployment

```bash
# Build and run all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Project Structure

```
I-Need-A-Dollar-Stock-Edition/
├── backend/                    # Spring Boot backend
│   ├── src/main/java/com/inad/stocks/
│   │   ├── config/            # Configuration classes
│   │   ├── controller/        # REST controllers
│   │   ├── dto/               # Data transfer objects
│   │   ├── entity/            # JPA entities
│   │   ├── integration/       # External API clients (Grok, Yahoo Finance)
│   │   ├── repository/        # JPA repositories
│   │   ├── scheduler/         # Trading cycle scheduler
│   │   ├── service/           # Business logic
│   │   └── websocket/         # WebSocket handlers
│   └── src/main/resources/
│       ├── application.yml    # Configuration
│       └── db/changelog/      # Liquibase migrations
├── frontend/                   # Next.js frontend
│   ├── app/                   # Next.js app router
│   ├── components/            # React components
│   └── lib/                   # API client, hooks
├── scripts/
│   └── start-local.sh         # Local development script
└── docker-compose.yml          # Docker configuration
```

## Future Roadmap

1. **CapTrader/IBKR Integration**: Replace Yahoo Finance mock with real broker API
2. **Real-time Price Streaming**: WebSocket connection to broker for live prices
3. **Order Execution**: Implement real order placement via IBKR Client Portal API
4. **Options Trading**: Extend to options strategies on tech stocks
5. **Portfolio Analytics**: Enhanced risk metrics and performance reporting

## License

MIT
