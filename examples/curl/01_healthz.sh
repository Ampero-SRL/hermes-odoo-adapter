#!/usr/bin/env bash
# Hit the adapter liveness endpoint.
#
# Expected output (HealthResponse model in main.py):
#   {"status":"healthy","service":"hermes-odoo-adapter","version":"2.0.0"}
#
# Failure modes:
#   - Connection refused      -> the adapter container is not up yet.
#   - HTTP 5xx                -> the FastAPI process started but cannot
#                                respond; check `docker compose logs adapter`.
#
# `/healthz` is the liveness probe and intentionally cheap — it does
# NOT verify backing subsystems. For that, see 02_readyz.sh.

set -euo pipefail
: "${ADAPTER_URL:=http://localhost:8080}"
curl -sf "${ADAPTER_URL}/healthz" | (command -v jq > /dev/null && jq . || cat)
