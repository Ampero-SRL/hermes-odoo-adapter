#!/usr/bin/env bash
# Poll a warehouse pick job's status. Pass the job_id returned by
# 01_warehouse_pick.sh as the first argument (or via JOB_ID env var).
#
# Service signature (hermes_msgs/srv/WarehousePickStatus):
#   request : string job_id
#   response: string status   # submitted | presenting | ready | failed
#             string slot     # e.g. "L1-S7" (Hanel) or "NULL-A1" (mock)
#             bool   tray_ready
#
# Expected response with NullWarehouseClient (returns ready immediately):
#   response: hermes_msgs.srv.WarehousePickStatus_Response(
#       status='ready', slot='NULL-A1', tray_ready=True)

set -euo pipefail
: "${JOB_ID:=${1:-}}"

if [[ -z "${JOB_ID}" ]]; then
    echo "Usage: $0 <job_id>   (or set JOB_ID=...)" >&2
    exit 2
fi

ros2 service call /hermes/warehouse/status \
    hermes_msgs/srv/WarehousePickStatus \
    "{job_id: '${JOB_ID}'}"
