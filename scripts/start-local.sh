#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# I-Need-A-Dollar - Agentic Trading System Local Startup
# 
# Starts the entire stack locally for development and testing:
# - PostgreSQL (with pgvector) via Docker
# - Redis (optional) via Docker
# - Agentic Trading System (all agents orchestrated)
# - Frontend with hot-reload
#
# Usage: ./scripts/start-local.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_DIR="/tmp/i-need-a-dollar"
LOG_DIR="$PROJECT_ROOT/.logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ─── HELPER FUNCTIONS ──────────────────────────────────────────────────────────

log_step() {
    local step=$1
    local total=$2
    local msg=$3
    printf "${CYAN}[%d/%d]${NC} %-35s" "$step" "$total" "$msg"
}

log_ok() {
    echo -e "${GREEN}OK${NC} $1"
}

log_fail() {
    echo -e "${RED}FAILED${NC}"
    echo -e "${RED}Error: $1${NC}"
    exit 1
}

log_warn() {
    echo -e "${YELLOW}$1${NC}"
}

log_info() {
    echo -e "${GRAY}$1${NC}"
}

# ─── CLEANUP ───────────────────────────────────────────────────────────────────

cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down Agentic Trading System...${NC}"
    
    # Kill all background processes
    if [ -d "$PID_DIR" ]; then
        for pidfile in "$PID_DIR"/*.pid; do
            if [ -f "$pidfile" ]; then
                pid=$(cat "$pidfile")
                if kill -0 "$pid" 2>/dev/null; then
                    echo -e "${GRAY}  Stopping PID $pid...${NC}"
                    kill "$pid" 2>/dev/null || true
                fi
                rm -f "$pidfile"
            fi
        done
        rmdir "$PID_DIR" 2>/dev/null || true
    fi
    
    # Stop database containers
    echo -e "${GRAY}Stopping database containers...${NC}"
    cd "$PROJECT_ROOT"
    docker compose stop postgres 2>/dev/null || true
    
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ─── KILL OLD PROCESSES ─────────────────────────────────────────────────────────

kill_old_processes() {
    local killed=0
    
    echo -e "${GRAY}  Scanning for old processes...${NC}"
    
    # Kill processes from old PID files
    if [ -d "$PID_DIR" ]; then
        for pidfile in "$PID_DIR"/*.pid; do
            if [ -f "$pidfile" ]; then
                pid=$(cat "$pidfile" 2>/dev/null)
                if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                    echo -e "${GRAY}    → PID $pid (from pidfile)${NC}"
                    kill -9 "$pid" 2>/dev/null || true
                    killed=$((killed + 1))
                fi
                rm -f "$pidfile"
            fi
        done
    fi
    
    # Kill any process on port 8000 (backend API)
    local port_8000_pids=$(lsof -ti :8000 2>/dev/null || true)
    if [ -n "$port_8000_pids" ]; then
        local count=$(echo "$port_8000_pids" | wc -l | tr -d ' ')
        echo -e "${GRAY}    → $count process(es) on port 8000${NC}"
        echo "$port_8000_pids" | xargs kill -9 2>/dev/null || true
        killed=$((killed + count))
    fi
    
    # Kill any process on port 3000 (frontend)
    local port_3000_pids=$(lsof -ti :3000 2>/dev/null || true)
    if [ -n "$port_3000_pids" ]; then
        local count=$(echo "$port_3000_pids" | wc -l | tr -d ' ')
        echo -e "${GRAY}    → $count process(es) on port 3000${NC}"
        echo "$port_3000_pids" | xargs kill -9 2>/dev/null || true
        killed=$((killed + count))
    fi
    
    # AGGRESSIVE: Kill ALL python main.py processes (matches both "python" and "Python")
    # Use pkill with case-insensitive matching
    local main_count=$(ps aux | grep -i "python.*main\.py" | grep -v grep | wc -l | tr -d ' ')
    if [ "$main_count" -gt 0 ]; then
        echo -e "${GRAY}    → $main_count python main.py process(es)${NC}"
        # Try multiple patterns to catch all variations
        pkill -9 -f "python main.py" 2>/dev/null || true
        pkill -9 -f "Python main.py" 2>/dev/null || true
        pkill -9 -f "python3 main.py" 2>/dev/null || true
        # Also kill by exact command matching
        ps aux | grep -i "python.*main\.py" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
        killed=$((killed + main_count))
    fi
    
    # Kill any lingering Next.js dev processes
    local next_count=$(pgrep -f "next dev" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$next_count" -gt 0 ]; then
        echo -e "${GRAY}    → $next_count Next.js dev process(es)${NC}"
        pkill -9 -f "next dev" 2>/dev/null || true
        killed=$((killed + next_count))
    fi
    
    # Kill any node processes running on our ports
    local node_pids=$(pgrep -f "node.*frontend" 2>/dev/null || true)
    if [ -n "$node_pids" ]; then
        local count=$(echo "$node_pids" | wc -l | tr -d ' ')
        echo -e "${GRAY}    → $count node frontend process(es)${NC}"
        echo "$node_pids" | xargs kill -9 2>/dev/null || true
        killed=$((killed + count))
    fi
    
    # Clean up PID directory
    rm -rf "$PID_DIR" 2>/dev/null || true
    mkdir -p "$PID_DIR"
    
    if [ $killed -gt 0 ]; then
        echo -e "${YELLOW}  Cleaned up $killed old process(es)${NC}"
        sleep 3  # Give time for ports to be released
        
        # Double-check ports are free
        if lsof -ti :8000 &>/dev/null || lsof -ti :3000 &>/dev/null; then
            echo -e "${YELLOW}  Ports still in use, waiting...${NC}"
            sleep 3
        fi
    else
        echo -e "${GREEN}  No old processes found${NC}"
    fi
    
    return 0
}

# ─── PREREQUISITE CHECKS ───────────────────────────────────────────────────────

check_prerequisites() {
    local errors=0
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}  ✗ Docker not installed${NC}"
        echo "    Install: https://docs.docker.com/get-docker/"
        errors=$((errors + 1))
    elif ! docker info &> /dev/null; then
        echo -e "${RED}  ✗ Docker daemon not running${NC}"
        echo "    Start Docker Desktop or run: sudo systemctl start docker"
        errors=$((errors + 1))
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}  ✗ Python 3 not installed${NC}"
        echo "    Install: brew install python@3.11"
        errors=$((errors + 1))
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}  ✗ Node.js not installed${NC}"
        echo "    Install: brew install node"
        errors=$((errors + 1))
    fi
    
    # Check if backend venv exists
    if [ ! -d "$PROJECT_ROOT/backend/.venv" ]; then
        echo -e "${YELLOW}  ! Python venv not found, creating...${NC}"
        cd "$PROJECT_ROOT/backend"
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -q -r requirements.txt
        echo -e "${GREEN}  ✓ Python venv created${NC}"
    fi
    
    # Check if node_modules exists
    if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
        echo -e "${YELLOW}  ! Node modules not found, installing...${NC}"
        cd "$PROJECT_ROOT/frontend"
        npm install --silent
        echo -e "${GREEN}  ✓ Node modules installed${NC}"
    fi
    
    if [ $errors -gt 0 ]; then
        log_fail "Missing $errors prerequisite(s)"
    fi
}

# ─── ENVIRONMENT SETUP ─────────────────────────────────────────────────────────

setup_environment() {
    cd "$PROJECT_ROOT"
    
    # Create .env if it doesn't exist
    if [ ! -f ".env" ]; then
        if [ -f "env.example" ]; then
            cp env.example .env
            echo -e "${YELLOW}  Created .env from env.example - please update API keys${NC}"
        else
            log_fail ".env file missing and no env.example found"
        fi
    fi
    
    # Load environment
    set -a
    source .env
    set +a
    
    # Override for local development
    export DATABASE_URL="postgresql+asyncpg://trading_user:${DB_PASSWORD:-trading_secret_2024}@localhost:5432/trading_platform"
    export REDIS_URL="redis://localhost:6379"
    export MODE="${MODE:-paper}"
    export CORS_ALLOW_ALL="true"
}

# ─── DATABASE STARTUP ──────────────────────────────────────────────────────────

start_databases() {
    cd "$PROJECT_ROOT"
    
    # Start only postgres container (redis is optional and may not exist)
    docker compose up -d postgres 2>/dev/null
}

wait_for_databases() {
    local max_attempts=30
    local attempt=0
    
    # Wait for PostgreSQL
    while [ $attempt -lt $max_attempts ]; do
        if docker compose exec -T postgres pg_isready -U trading_user -d trading_platform &>/dev/null; then
            break
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_fail "PostgreSQL failed to start"
    fi
}

# ─── MIGRATIONS ────────────────────────────────────────────────────────────────

run_migrations() {
    cd "$PROJECT_ROOT/backend"
    source .venv/bin/activate
    
    # Run migrations
    python migrations/run_migrations.py 2>&1 | grep -E "^(✅|🚀|📋|✓|Migration)" || true
}

# ─── SERVICE STARTUP ───────────────────────────────────────────────────────────

start_backend_services() {
    mkdir -p "$PID_DIR"
    mkdir -p "$LOG_DIR"
    
    cd "$PROJECT_ROOT/backend"
    source .venv/bin/activate
    
    # Agentic Trading System (main.py runs everything)
    # It starts the orchestrator + all agents + API server
    python main.py \
        > "$LOG_DIR/agentic_system.log" 2>&1 &
    echo $! > "$PID_DIR/agentic_system.pid"
    
    # Wait a moment for services to start
    sleep 3
    
    # Verify gateway is responding
    local attempt=0
    while [ $attempt -lt 15 ]; do
        if curl -s http://localhost:8000/health &>/dev/null; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    
    log_warn "(API may still be starting, check logs)"
}

start_frontend() {
    cd "$PROJECT_ROOT/frontend"
    
    # Start frontend in foreground (this blocks)
    npm run dev
}

show_agent_info() {
    echo ""
    echo -e "${PURPLE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║                ${BOLD}EMERGENT AI SWARM${NC}${PURPLE}                              ║${NC}"
    echo -e "${PURPLE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}🔍 Scout${NC}       Alpha hunter - scans X for opportunities"
    echo -e "  ${CYAN}🔬 Analyst${NC}     Deep researcher - due diligence"
    echo -e "  ${CYAN}🔮 Oracle${NC}      Sentiment reader - market vibes"
    echo -e "  ${CYAN}🎯 Tactician${NC}   Strategy mind - makes decisions"
    echo -e "  ${CYAN}⚡ Operator${NC}    Trade executor - handles orders"
    echo -e "  ${CYAN}🧙 Sage${NC}        Learning & memory - finds patterns"
    echo ""
    echo -e "  ${GRAY}All agents use Grok for web/X search - no other APIs${NC}"
    echo ""
}

# ─── MAIN ──────────────────────────────────────────────────────────────────────

main() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║      ${BOLD}I-Need-A-Dollar${NC}${CYAN} - Emergent AI Swarm                     ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    cd "$PROJECT_ROOT"
    
    # Step 1: Kill old processes
    log_step 1 7 "Cleaning up old processes..."
    kill_old_processes
    log_ok ""
    
    # Step 2: Prerequisites
    log_step 2 7 "Checking prerequisites..."
    check_prerequisites
    log_ok ""
    
    # Step 3: Environment
    log_step 3 7 "Setting up environment..."
    setup_environment
    log_ok "(Mode: ${MODE:-paper})"
    
    # Step 4: Start databases
    log_step 4 7 "Starting databases..."
    start_databases
    log_ok "(pgvector enabled)"
    
    # Step 5: Wait for databases
    log_step 5 7 "Waiting for databases..."
    wait_for_databases
    log_ok "(PostgreSQL ready)"
    
    # Step 6: Run migrations
    log_step 6 7 "Running migrations..."
    run_migrations
    log_ok ""
    
    # Step 7: Start backend services
    log_step 7 7 "Starting Emergent AI Swarm..."
    start_backend_services
    log_ok ""
    
    # Show agent info
    show_agent_info
    
    # Show status
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}All services running!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${CYAN}Frontend:${NC}       http://localhost:3000"
    echo -e "  ${CYAN}API:${NC}            http://localhost:8000"
    echo -e "  ${CYAN}API Docs:${NC}       http://localhost:8000/docs"
    echo -e "  ${CYAN}WebSocket:${NC}      ws://localhost:8000/ws/swarm"
    echo ""
    echo -e "  ${CYAN}Live Stream:${NC}    http://localhost:3000/stream"
    echo -e "  ${CYAN}Evolution:${NC}      http://localhost:3000/evolution"
    echo -e "  ${CYAN}Agent Logbook:${NC}  http://localhost:3000/agents"
    echo -e "  ${CYAN}Universe:${NC}       http://localhost:3000/universe"
    echo -e "  ${CYAN}Strategies:${NC}     http://localhost:3000/strategies"
    echo ""
    echo -e "  ${GRAY}Logs:${NC}           $LOG_DIR/agentic_system.log"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
    echo ""
    
    # Start frontend (blocks until Ctrl+C)
    start_frontend
}

main "$@"
