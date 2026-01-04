# I Need A Dollar - Trading Platform

A production-grade autonomous trading platform with AI-powered sentiment analysis, built with Spring Boot and Next.js.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
│                   (Next.js + React + Tailwind)                       │
│                        Port 3000                                     │
├─────────────────────────────────────────────────────────────────────┤
│                              ↕                                       │
│                     REST API + WebSocket                             │
├─────────────────────────────────────────────────────────────────────┤
│                           BACKEND                                    │
│                    (Spring Boot + Liquibase)                         │
│                        Port 8080                                     │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐          │
│  │ Controllers │   Services  │ Repositories│ WebSocket   │          │
│  └─────────────┴─────────────┴─────────────┴─────────────┘          │
│  ┌─────────────┬─────────────┐                                       │
│  │   Binance   │   Grok AI   │  (External Integrations)             │
│  └─────────────┴─────────────┘                                       │
├─────────────────────────────────────────────────────────────────────┤
│                           DATABASE                                   │
│                      (PostgreSQL + Liquibase)                        │
│                        Port 5432                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

- **Backend**: Java 21, Spring Boot 3.2, Spring Data JPA, Spring WebSocket
- **Database**: PostgreSQL 15, Liquibase for migrations
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS
- **External APIs**: Binance Futures, Grok xAI

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
npm run dev
```

### Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8080
- **API Docs (Swagger)**: http://localhost:8080/swagger-ui.html
- **Health Check**: http://localhost:8080/health

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
- `GET /api/debug/prices` - Debug price data

## WebSocket Endpoints

- `ws://localhost:8080/ws/equity` - Real-time equity streaming
- `ws://localhost:8080/ws` - General event streaming

## Environment Variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `jdbc:postgresql://localhost:5432/trading` | Database connection URL |
| `DB_USERNAME` | `postgres` | Database username |
| `DB_PASSWORD` | `postgres` | Database password |
| `XAI_API_KEY` | - | Grok xAI API key |
| `BINANCE_API_KEY` | - | Binance API key (optional) |
| `BINANCE_API_SECRET` | - | Binance API secret (optional) |
| `MODE` | `paper` | Trading mode (paper/live) |
| `CYCLE_INTERVAL` | `600000` | Trading cycle interval (ms) |
| `STARTING_CAPITAL` | `100000` | Starting capital (USDT) |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8080` | Backend API URL |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8080/ws/equity` | WebSocket URL |

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
I-Need-A-Dollar/
├── backend/                    # Spring Boot backend
│   ├── src/main/java/com/trading/
│   │   ├── config/            # Configuration classes
│   │   ├── controller/        # REST controllers
│   │   ├── dto/               # Data transfer objects
│   │   ├── entity/            # JPA entities
│   │   ├── integration/       # External API clients
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
├── old/                        # Backup of Python implementation
│   ├── backend-python/        # Original FastAPI backend
│   └── frontend-nextjs/       # Original frontend
├── scripts/
│   └── start-local.sh         # Local development script
└── docker-compose.yml          # Docker configuration
```

## Legacy Python Implementation

The original Python/FastAPI implementation is preserved in the `old/` directory for reference:

- `old/backend-python/` - FastAPI backend with asyncpg
- `old/frontend-nextjs/` - Original Next.js frontend

## License

MIT
