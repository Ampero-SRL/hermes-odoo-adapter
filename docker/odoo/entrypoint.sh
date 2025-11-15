#!/bin/bash
set -euo pipefail

CMD=${1:-odoo}
shift || true
DB_NAME=${ODOO_DB:-odoo}
INIT_MARKER="/var/lib/odoo/.hermes_seed_${DB_NAME}"
MODULE=${HERMES_INIT_MODULE:-hermes_electrical_seed}

# Wait for Postgres to be ready
wait_for_postgres() {
  local max_attempts=30
  local attempt=1
  local db_host="${HOST:-postgres}"
  local db_port="5432"
  echo "[HERMES] Waiting for PostgreSQL at ${db_host}:${db_port} to be ready..."

  while [ $attempt -le $max_attempts ]; do
    if python3 -c "import socket; s = socket.socket(); s.settimeout(1); s.connect(('$db_host', $db_port)); s.close()" > /dev/null 2>&1; then
      echo "[HERMES] PostgreSQL port is open, waiting 2 more seconds for full readiness..."
      sleep 2
      echo "[HERMES] PostgreSQL is ready!"
      return 0
    fi
    echo "[HERMES] PostgreSQL not ready yet (attempt $attempt/$max_attempts)..."
    sleep 2
    attempt=$((attempt + 1))
  done

  echo "[HERMES] ERROR: PostgreSQL failed to become ready"
  return 1
}

if [ "$CMD" = "odoo" ]; then
  wait_for_postgres

  if [ ! -f "$INIT_MARKER" ]; then
    echo "[HERMES] Initialising database with base modules first..."
    odoo -d "$DB_NAME" -i base,stock,mrp --without-demo=all --stop-after-init
    if [ $? -ne 0 ]; then
      echo "[HERMES] ERROR: Base database initialization failed"
      exit 1
    fi
    echo "[HERMES] Base modules installed successfully"

    echo "[HERMES] Installing custom module ${MODULE}..."
    odoo -d "$DB_NAME" -i "$MODULE" --without-demo=all --stop-after-init
    if [ $? -eq 0 ]; then
      echo "[HERMES] Custom module installation successful"
      touch "$INIT_MARKER"
    else
      echo "[HERMES] ERROR: Custom module installation failed"
      exit 1
    fi
  else
    echo "[HERMES] Database already initialized (marker file exists)"
  fi
  echo "[HERMES] Starting Odoo"
  exec odoo "$@"
fi

exec "$CMD" "$@"
