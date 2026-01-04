#!/bin/bash
set -e

echo "=== I Need A Dollar - Local Development ==="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Add Java to PATH if installed via Homebrew
if [ -d "/opt/homebrew/opt/openjdk@21/bin" ]; then
    export PATH="/opt/homebrew/opt/openjdk@21/bin:$PATH"
    export JAVA_HOME="/opt/homebrew/opt/openjdk@21"
elif [ -d "/usr/local/opt/openjdk@21/bin" ]; then
    export PATH="/usr/local/opt/openjdk@21/bin:$PATH"
    export JAVA_HOME="/usr/local/opt/openjdk@21"
fi

# Check Java installation
if ! command -v java &> /dev/null; then
    echo -e "${RED}Error: Java not found!${NC}"
    echo ""
    echo "Please install Java 21:"
    echo "  brew install openjdk@21"
    echo ""
    echo "Or use Docker instead:"
    echo "  docker-compose up"
    exit 1
fi

echo -e "${GREEN}Java found: $(java -version 2>&1 | head -1)${NC}"

# Kill any existing processes on required ports
echo ""
echo -e "${YELLOW}Cleaning up existing processes...${NC}"
lsof -ti:8080 | xargs kill -9 2>/dev/null && echo "  Killed process on port 8080" || true
lsof -ti:3000 | xargs kill -9 2>/dev/null && echo "  Killed process on port 3000" || true
pkill -f "gradlew" 2>/dev/null && echo "  Killed Gradle processes" || true
pkill -f "next-server" 2>/dev/null && echo "  Killed Next.js processes" || true
echo -e "${GREEN}Cleanup complete${NC}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}Shutdown complete${NC}"
}

trap cleanup EXIT

# Check if PostgreSQL is running
echo -e "${YELLOW}Checking PostgreSQL...${NC}"
if ! pg_isready -q 2>/dev/null && ! docker-compose ps postgres 2>/dev/null | grep -q "Up"; then
    echo "Starting PostgreSQL via Docker..."
    docker-compose up -d postgres
    echo "Waiting for PostgreSQL to be ready..."
    sleep 5
    until docker-compose exec -T postgres pg_isready -q 2>/dev/null; do
        echo "  Waiting for PostgreSQL..."
        sleep 2
    done
fi
echo -e "${GREEN}PostgreSQL is ready${NC}"

# Load .env file if it exists
if [ -f ".env" ]; then
    echo "Loading environment from .env..."
    set -a
    source .env
    set +a
    # Debug: verify key variables are loaded (show only length, not actual values)
    if [ -n "$XAI_API_KEY" ]; then
        echo -e "${GREEN}  XAI_API_KEY loaded (${#XAI_API_KEY} chars)${NC}"
    else
        echo -e "${RED}  XAI_API_KEY is NOT set in .env${NC}"
    fi
else
    echo -e "${YELLOW}Warning: .env file not found. Using defaults.${NC}"
fi

# Start Spring Boot backend
echo ""
echo -e "${YELLOW}Starting Spring Boot backend...${NC}"
cd backend

# Check if Gradle wrapper jar exists, download if not
if [ ! -f "gradle/wrapper/gradle-wrapper.jar" ]; then
    echo "Downloading Gradle wrapper..."
    mkdir -p gradle/wrapper
    curl -sL -o gradle/wrapper/gradle-wrapper.jar \
        "https://github.com/gradle/gradle/raw/v8.5.0/gradle/wrapper/gradle-wrapper.jar" 2>/dev/null || \
    wget -q -O gradle/wrapper/gradle-wrapper.jar \
        "https://github.com/gradle/gradle/raw/v8.5.0/gradle/wrapper/gradle-wrapper.jar" 2>/dev/null || \
    echo -e "${RED}Failed to download Gradle wrapper. Please install Gradle manually.${NC}"
fi

./gradlew bootRun --console=plain &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
echo "Waiting for backend to start..."
MAX_WAIT=120
WAIT_COUNT=0
until curl -s http://localhost:8080/health > /dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo -e "${RED}Backend failed to start within ${MAX_WAIT} seconds${NC}"
        exit 1
    fi
    if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
        echo "  Still waiting... (${WAIT_COUNT}s)"
    fi
done
echo -e "${GREEN}Backend ready at http://localhost:8080${NC}"
echo -e "${GREEN}API docs at http://localhost:8080/swagger-ui.html${NC}"

# Start frontend
echo ""
echo -e "${YELLOW}Starting Next.js frontend...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for frontend
sleep 3
echo -e "${GREEN}Frontend ready at http://localhost:3000${NC}"

echo ""
echo "============================================"
echo -e "${GREEN}All services started!${NC}"
echo ""
echo "  Backend:  http://localhost:8080"
echo "  Frontend: http://localhost:3000"
echo "  API Docs: http://localhost:8080/swagger-ui.html"
echo ""
echo "Press Ctrl+C to stop all services"
echo "============================================"
echo ""

# Wait for processes
wait
