#!/usr/bin/env bash
# Queue a full Odoo -> Orion-LD inventory sync. The sync runs in the
# background; this call only acknowledges that it was queued.
#
# Expected response (main.py:565-575):
#   {"message": "Inventory synchronization queued"}
#
# Follow with `/admin/inventory/status` to watch the worker complete.

set -euo pipefail
: "${ADAPTER_URL:=http://localhost:8080}"

curl -sS \
    -X GET "${ADAPTER_URL}/admin/inventory/sync" \
    | (command -v jq > /dev/null && jq . || cat)
