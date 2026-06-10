#!/usr/bin/env bash
# Trigger a full Odoo -> Orion-LD inventory sync. Useful after seeding
# the Odoo mock with new SKUs.
#
# Expected output:
#   {"started":true,"items_queued":<N>,...}
#
# Follow up with 06b (admin/inventory/status) to see when the sync completes.

set -euo pipefail
: "${ADAPTER_URL:=http://localhost:8080}"

curl -sS \
    -X GET "${ADAPTER_URL}/admin/inventory/sync" \
    | (command -v jq > /dev/null && jq . || cat)
