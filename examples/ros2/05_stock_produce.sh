#!/usr/bin/env bash
# Increment finished-product stock at end of assembly.
#
# Service signature (hermes_msgs/srv/ProduceStock):
#   request : string project_id, string sku, int32 quantity
#   response: bool   success
#
# Expected response:
#   response: hermes_msgs.srv.ProduceStock_Response(success=True)

set -euo pipefail
: "${PROJECT_ID:=urn:ngsi-ld:Project:demo-project-1}"
: "${SKU:=PANEL-P1}"
: "${QUANTITY:=1}"

ros2 service call /hermes/stock/produce \
    hermes_msgs/srv/ProduceStock \
    "{project_id: '${PROJECT_ID}', sku: '${SKU}', quantity: ${QUANTITY}}"
