#!/usr/bin/env bash
# Poll a warehouse pick job's status. Pass the job_id returned by
# 01_warehouse_pick.sh as the first argument (or via JOB_ID env var).
#
# Expected output (NullWarehouseClient, typically immediate):
#   response: hermes_msgs.srv.WarehousePickStatus_Response(
#       status='ready', slot=0, tray_ready=True, error='')

set -euo pipefail
: "${JOB_ID:=${1:-}}"

if [[ -z "${JOB_ID}" ]]; then
    echo "Usage: $0 <job_id>   (or set JOB_ID=...)" >&2
    exit 2
fi

ros2 service call /hermes/warehouse/status \
    hermes_msgs/srv/WarehousePickStatus \
    "{job_id: '${JOB_ID}'}"
