#!/usr/bin/env bash
# Decrement stock through the adapter's HTTP face (equivalent to the
# /hermes/stock/consume ROS 2 service, for clients that aren't on DDS).
#
# Request body (ConsumeRequest model in main.py:259-272):
#   {"project_id": "...", "sku": "...", "quantity": <int>}
#
# Expected response shape (main.py:476-480):
#   {
#     "status": "ok",
#     "message": "Consumed 1 units of SCH-REL-24V",
#     "details": { ... Odoo stock-move result ... }
#   }

set -euo pipefail
: "${ADAPTER_URL:=http://localhost:8080}"
: "${PROJECT_ID:=urn:ngsi-ld:Project:demo-ctrl-1}"
: "${SKU:=SCH-REL-24V}"
: "${QUANTITY:=1}"

curl -sS \
    -H "Content-Type: application/json" \
    -X POST "${ADAPTER_URL}/api/consume" \
    -d "{
        \"project_id\": \"${PROJECT_ID}\",
        \"sku\": \"${SKU}\",
        \"quantity\": ${QUANTITY}
    }" \
    | (command -v jq > /dev/null && jq . || cat)
