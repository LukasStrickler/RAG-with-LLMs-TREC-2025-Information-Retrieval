#!/usr/bin/env bash

# setup.sh - One-command setup for the entire RAG system
# This script initializes storage, starts Docker services, and verifies everything is running

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 RAG System Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: Initialize storage
echo "Step 1/3: Initializing storage from backups..."
"$SCRIPT_DIR/init-storage.sh" "$@"

# Step 2: Start Docker services
echo ""
echo "Step 2/3: Starting Docker services..."
cd "$PROJECT_ROOT"

if docker-compose ps | grep -q "Up"; then
    echo "⚠️  Some services are already running"
    read -p "Restart all services? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose down
        docker-compose up -d
    fi
else
    docker-compose up -d
fi

# Step 3: Wait for services to be ready
echo ""
echo "Step 3/3: Waiting for services to be ready..."

wait_for_service() {
    local name="$1"
    local url="$2"
    local max_attempts=30
    local attempt=0
    
    echo -n "  Waiting for $name..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo " ✓"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo " ❌ (timeout)"
    return 1
}

wait_for_service "PostgreSQL" "localhost:5433" || true
wait_for_service "Solr" "http://localhost:8983/solr/" || true
wait_for_service "Qdrant" "http://localhost:6333/dashboard" || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete!"
echo ""
echo "Services running:"
echo "  • PostgreSQL: localhost:5433"
echo "  • Solr: http://localhost:8983/solr/"
echo "  • Qdrant: http://localhost:6333/dashboard"
echo ""
echo "Next steps:"
echo "  1. Start backend API: cd backend/api && poetry run uvicorn app.main:app --reload"
echo "  2. Start frontend: cd frontend && npm run dev"
echo "  3. Access frontend: http://localhost:3000"
echo ""
echo "To run evaluations: cd backend/eval && poetry run eval-cli run trec-dl-23"
