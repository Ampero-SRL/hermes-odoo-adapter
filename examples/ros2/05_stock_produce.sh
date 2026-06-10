#!/usr/bin/env bash
# Increment finished-product stock at end of assembly.
#
# Expected output:
#   response: hermes_msgs.srv.ProduceStock_Response(success=True, error='')

set -euo pipefail
: "${SKU:=PANEL-P1}"
: "${QUANTITY:=1}"
: "${PROJECT_ID:=urn:ngsi-ld:Project:demo-project-1}"
: "${OPERATOR:=assembly-cell-1}"

ros2 service call /hermes/stock/produce \
    hermes_msgs/srv/ProduceStock \
    "{sku: '${SKU}', quantity: ${QUANTITY}, project_id: '${PROJECT_ID}', operator: '${OPERATOR}'}"
