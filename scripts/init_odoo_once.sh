#!/bin/bash
# Initialization script that runs once to set up Odoo with HERMES products

INIT_FLAG="/tmp/.hermes_odoo_initialized"
ODOO_BASE_URL="${ODOO_URL:-http://odoo:8069/jsonrpc}"
ODOO_BASE_URL="${ODOO_BASE_URL%/jsonrpc}"
READY_URL="${ODOO_BASE_URL}/web/database/selector"
ODOO_DB_NAME="${ODOO_DB:-odoo}"
ODOO_USER_NAME="${ODOO_USER:-admin}"
ODOO_PASSWORD_VALUE="${ODOO_PASSWORD:-admin}"
READY=0

# Check if already initialized
if [ -f "$INIT_FLAG" ]; then
    echo "✓ HERMES Odoo already initialized"
    exit 0
fi

echo "🔄 Initializing HERMES Odoo environment..."

# Wait for Odoo to be ready
echo "⏳ Waiting for Odoo to be ready at ${READY_URL}..."
for i in {1..30}; do
    if curl -fsS "$READY_URL" > /dev/null 2>&1; then
        echo "✓ Odoo is ready"
        READY=1
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 2
done

if [ "$READY" -ne 1 ]; then
    echo "❌ Odoo did not become ready at ${READY_URL}"
    exit 1
fi

if ODOO_BASE_URL="$ODOO_BASE_URL" ODOO_DB_NAME="$ODOO_DB_NAME" ODOO_USER_NAME="$ODOO_USER_NAME" ODOO_PASSWORD_VALUE="$ODOO_PASSWORD_VALUE" python3 - <<'PY'
import os
import sys
import xmlrpc.client

required_skus = [
    "CTRL-PANEL-A1",
    "EL-SAFETY-RELAY",
    "EL-IFACE-RELAY",
    "EL-CONTACTOR",
    "EL-AUX-CONTACT",
    "EL-FUSE-CARRIER",
]

base_url = os.environ["ODOO_BASE_URL"]
db = os.environ["ODOO_DB_NAME"]
user = os.environ["ODOO_USER_NAME"]
password = os.environ["ODOO_PASSWORD_VALUE"]

common = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/common")
uid = common.authenticate(db, user, password, {})
if not uid:
    sys.exit(1)

models = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/object")
found = models.execute_kw(
    db,
    uid,
    password,
    "product.product",
    "search_read",
    [[("default_code", "in", required_skus)]],
    {"fields": ["default_code"], "limit": len(required_skus)},
)

found_skus = {row.get("default_code") for row in found}
sys.exit(0 if found_skus.issuperset(required_skus) else 1)
PY
then
    touch "$INIT_FLAG"
    echo "✓ HERMES demo products already present in Odoo"
    exit 0
fi

# Run the seed script
echo "📦 Seeding HERMES products..."
cd /app && python3 scripts/seed_real_odoo.py

if [ $? -eq 0 ]; then
    touch "$INIT_FLAG"
    echo "✅ HERMES Odoo initialization completed"
else
    echo "❌ Initialization failed"
    exit 1
fi
