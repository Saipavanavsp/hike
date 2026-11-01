#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head

if [ "$SEED_ON_START" = "true" ]; then
  echo "Seeding (only if database is empty)..."
  python -m seed.seed --if-empty
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
