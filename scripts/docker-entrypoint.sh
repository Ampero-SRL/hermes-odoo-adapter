#!/bin/bash
set -e

echo "🚀 Starting HERMES Odoo Adapter..."

# Run initialization script (only runs once)
if [ -x /app/scripts/init_odoo_once.sh ]; then
    /app/scripts/init_odoo_once.sh || echo "⚠️  Initialization had issues, continuing anyway..."
fi

# Execute the main application
exec "$@"
