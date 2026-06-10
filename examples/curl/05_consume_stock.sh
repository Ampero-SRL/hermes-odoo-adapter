#!/usr/bin/env bash
# Decrement stock through the adapter's HTTP face (equivalent to the
# /hermes/stock/consume ROS 2 service, for clients that aren't on DDS).
#
# Expected output:
#   {"success":true,"sku":"ARTICOLO5","new_quantity":11,...}

set -euo pipefail
: "${ADAPTER_URL:=http://localhost:8080}"
: "${SKU:=ARTICOLO5}"
: "${QUANTITY:=1}"
: "${PROJECT_ID:=urn:ngsi-ld:Project:demo-project-1}"

curl -sS \
    -H "Content-Type: application/json" \
    -X POST "${ADAPTER_URL}/api/consume" \
    -d "{
        \"sku\": \"${SKU}\",
        \"quantity\": ${QUANTITY},
        \"project_id\": \"${PROJECT_ID}\",
        \"operator\": \"example-script\"
    }" \
    | (command -v jq > /dev/null && jq . || cat)
