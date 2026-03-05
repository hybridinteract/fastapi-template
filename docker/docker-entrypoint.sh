#!/bin/bash
# Docker Entrypoint Script

set -e

echo "=========================================="
echo "FastAPI Application Starting..."
echo "Environment: ${ENVIRONMENT:-development}"
echo "=========================================="

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."

wait_for_postgres() {
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if python <<END
import asyncio
import asyncpg
import sys

async def check():
    try:
        conn = await asyncpg.connect(
            host='${POSTGRES_HOST}',
            port=${POSTGRES_PORT},
            user='${POSTGRES_USER}',
            password='${POSTGRES_PASSWORD}',
            database='${POSTGRES_DB}',
            timeout=5
        )
        await conn.close()
        return True
    except:
        return False

sys.exit(0 if asyncio.run(check()) else 1)
END
        then
            echo "✅ PostgreSQL is ready!"
            return 0
        fi
        
        echo "  Attempt $attempt/$max_attempts..."
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo "❌ PostgreSQL connection failed"
    return 1
}

wait_for_postgres || exit 1

# Run migrations
echo ""
echo "🔄 Running database migrations..."

if [ -f "alembic.ini" ] && [ -d "migrations/versions" ]; then
    alembic upgrade head
    echo "✅ Migrations completed"
else
    echo "⚠️ No migrations found, skipping"
fi

# Create logs directory
mkdir -p /app/logs || true

echo ""
echo "=========================================="
echo "🚀 Starting application..."
echo "=========================================="

exec "$@"
