#!/usr/bin/env bash
# Hit the adapter liveness endpoint.
#
# Expected output:
#   {"status":"ok","version":"2.0.0","subsystems":{"odoo":"ok","orion":"ok","warehouse":"ok (NullWarehouseClient)"}}
#
# Failure modes:
#   - Connection refused      -> the adapter container is not up yet
#   - {"status":"error",...}  -> one subsystem failed; check /readyz for detail

set -euo pipefail
: "${ADAPTER_URL:=http://localhost:8080}"
curl -sf "${ADAPTER_URL}/healthz" | (command -v jq > /dev/null && jq . || cat)
