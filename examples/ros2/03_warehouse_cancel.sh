#!/usr/bin/env bash
# Cancel a pending warehouse pick job. Pass the job_id as the first
# argument.
#
# Service signature (hermes_msgs/srv/WarehousePickCancel):
#   request : string job_id
#   response: bool   success
#
# Expected response:
#   response: hermes_msgs.srv.WarehousePickCancel_Response(success=True)

set -euo pipefail
: "${JOB_ID:=${1:-}}"

if [[ -z "${JOB_ID}" ]]; then
    echo "Usage: $0 <job_id>   (or set JOB_ID=...)" >&2
    exit 2
fi

ros2 service call /hermes/warehouse/cancel \
    hermes_msgs/srv/WarehousePickCancel \
    "{job_id: '${JOB_ID}'}"
