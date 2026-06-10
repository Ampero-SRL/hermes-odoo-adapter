#!/usr/bin/env bash
# Decrement stock after a cobot pick. Triggers an Odoo stock move + an
# NGSI-LD InventoryItem.quantity PATCH against Orion-LD.
#
# Expected output:
#   response: hermes_msgs.srv.ConsumeStock_Response(success=True, error='')

set -euo pipefail
: "${SKU:=ARTICOLO5}"
: "${QUANTITY:=1}"
: "${PROJECT_ID:=urn:ngsi-ld:Project:demo-project-1}"
: "${OPERATOR:=cobot-1}"

ros2 service call /hermes/stock/consume \
    hermes_msgs/srv/ConsumeStock \
    "{sku: '${SKU}', quantity: ${QUANTITY}, project_id: '${PROJECT_ID}', operator: '${OPERATOR}'}"
