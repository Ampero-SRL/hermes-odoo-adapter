#!/usr/bin/env bash
# Hit the adapter readiness endpoint — checks each backing subsystem.
#
# Expected output (success):
#   {"ready":true,"checks":{"odoo":{"ok":true,...},"orion":{"ok":true,...},
#                            "warehouse":{"ok":true,"backend":"NullWarehouseClient",...}}}

set -euo pipefail
: "${ADAPTER_URL:=http://localhost:8080}"
curl -sf "${ADAPTER_URL}/readyz" | (command -v jq > /dev/null && jq . || cat)
