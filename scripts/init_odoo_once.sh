#!/bin/bash
# Initialization script that runs once to set up Odoo with HERMES products

INIT_FLAG="/tmp/.hermes_odoo_initialized"

# Check if already initialized
if [ -f "$INIT_FLAG" ]; then
    echo "✓ HERMES Odoo already initialized"
    exit 0
fi

echo "🔄 Initializing HERMES Odoo environment..."

# Wait for Odoo to be ready
echo "⏳ Waiting for Odoo to be ready..."
for i in {1..30}; do
    if curl -s http://odoo:8069/web/database/selector > /dev/null 2>&1; then
        echo "✓ Odoo is ready"
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 2
done

# Run the seed script
echo "📦 Seeding HERMES products..."
cd /app && python scripts/seed_real_odoo.py

if [ $? -eq 0 ]; then
    touch "$INIT_FLAG"
    echo "✅ HERMES Odoo initialization completed"
else
    echo "❌ Initialization failed"
    exit 1
fi
