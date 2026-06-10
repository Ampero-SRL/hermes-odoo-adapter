#!/usr/bin/env bash
# Decrement stock after a cobot pick. Triggers an Odoo stock move + an
# NGSI-LD InventoryItem PATCH against Orion-LD + publishes an
# InventoryUpdate event on /hermes/inventory_updates.
#
# Service signature (hermes_msgs/srv/ConsumeStock):
#   request : string project_id, string sku, int32 quantity
#   response: bool    success
#             float64 remaining   # remaining stock after the move
#
# Expected response (Odoo mock with seeded data):
#   response: hermes_msgs.srv.ConsumeStock_Response(
#       success=True, remaining=11.0)

set -euo pipefail
: "${PROJECT_ID:=urn:ngsi-ld:Project:demo-project-1}"
: "${SKU:=ARTICOLO5}"
: "${QUANTITY:=1}"

ros2 service call /hermes/stock/consume \
    hermes_msgs/srv/ConsumeStock \
    "{project_id: '${PROJECT_ID}', sku: '${SKU}', quantity: ${QUANTITY}}"
