#!/usr/bin/env bash
# Send a WarehousePick request to the adapter. Empty job_id -> the
# adapter assigns one (returned in the response).
#
# Run this from a Vulcanexus / ROS 2 Humble shell that has sourced the
# vendored hermes_msgs workspace. The simplest way:
#
#   docker compose -f docker/docker-compose.demo.yml exec adapter \
#       bash -lc 'source /opt/ros/humble/setup.bash && \
#                 source /opt/hermes_ws/install/setup.bash && \
#                 bash /app/examples/ros2/01_warehouse_pick.sh'
#
# Expected output (NullWarehouseClient):
#   response: hermes_msgs.srv.WarehousePick_Response(success=True, job_id='M<...>', error='')

set -euo pipefail
: "${SKU:=ARTICOLO5}"
: "${QUANTITY:=1}"

ros2 service call /hermes/warehouse/pick \
    hermes_msgs/srv/WarehousePick \
    "{job_id: '', sku: '${SKU}', quantity: ${QUANTITY}}"
