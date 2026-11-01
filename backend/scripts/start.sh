#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head

if [ "$SEED_ON_START" = "true" ]; then
  echo "Seeding (only if database is empty)..."
  python -m seed.seed --if-empty
fi

# Without a worker (TASKS_EAGER=true) there is no scheduler, so apply the retention
# policy on every start instead of daily.
if [ "$TASKS_EAGER" = "true" ]; then
  echo "Applying data retention policy..."
  python -m app.services.retention || echo "retention sweep failed; continuing"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
