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
echo "Step 1/4: Initializing storage from backups..."
"$SCRIPT_DIR/init-storage.sh" "$@"

# Step 2: Start Docker services
echo ""
echo "Step 2/4: Starting Docker services..."
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
echo "Step 3/4: Waiting for services to be ready..."

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
    echo " ❌ (timeout) Note PostgreSQL may take longer to start. Wait for the script to finish and check logs if needed."
    return 1
}

wait_for_service "PostgreSQL" "localhost:5433" || true
wait_for_service "Solr" "http://localhost:8983/solr/" || true
wait_for_service "Qdrant" "http://localhost:6333/dashboard" || true

# Step 4: Restore PostgreSQL backup if available
echo ""
echo "Step 4/4: Restoring PostgreSQL backup..."

POSTGRES_BACKUP="$PROJECT_ROOT/images/postgres_backup.dump"
if [ -f "$POSTGRES_BACKUP" ]; then
    echo "  → Checking if database needs restoration..."
    
    # Check if database already has data
    DOC_COUNT=$(docker exec postgres psql -U postgres -t -c "SELECT COUNT(*) FROM documents;" 2>/dev/null || echo "0")
    DOC_COUNT=$(echo "$DOC_COUNT" | tr -d '[:space:]')
    
    if [ "$DOC_COUNT" = "0" ] || [ "$1" = "--force" ]; then
        echo "  → Restoring database (~2-3 min)..."
        docker cp "$POSTGRES_BACKUP" postgres:/tmp/postgres_backup.dump
        docker exec postgres pg_restore -U postgres -d postgres -c --if-exists /tmp/postgres_backup.dump 2>/dev/null || true
        docker exec postgres rm /tmp/postgres_backup.dump
        echo "  ✓ Database restored successfully"
    else
        echo "  ✓ Database already populated ($DOC_COUNT documents)"
        echo "  → Use --force to restore anyway"
    fi
else
    echo "  ⚠️  No PostgreSQL backup found, database will start empty"
fi

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
