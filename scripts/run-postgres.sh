#!/usr/bin/env bash
set -euo pipefail

NAME="${NAME:-finance-postgres}"
VOLUME="${VOLUME:-finance_postgres_data}"
PORT="${PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-finance}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-finance}"
POSTGRES_DB="${POSTGRES_DB:-finances}"
IMAGE="${IMAGE:-postgres:16}"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  if docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
    echo "Postgres container '$NAME' is already running."
    exit 0
  fi
  docker start "$NAME" >/dev/null
  echo "Started existing container '$NAME'."
  echo "DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${PORT}/${POSTGRES_DB}"
  exit 0
fi

if ! docker volume inspect "$VOLUME" >/dev/null 2>&1; then
  docker volume create "$VOLUME" >/dev/null
fi

docker run -d --name "$NAME" \
  -e POSTGRES_USER="$POSTGRES_USER" \
  -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  -e POSTGRES_DB="$POSTGRES_DB" \
  -p "${PORT}:5432" \
  -v "${VOLUME}:/var/lib/postgresql/data" \
  "$IMAGE" >/dev/null

echo "Started new container '$NAME' on port $PORT."
echo "DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${PORT}/${POSTGRES_DB}"
