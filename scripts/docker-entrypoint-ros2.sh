#!/bin/bash
set -e

echo "Starting HERMES Odoo Adapter v2.0 (ROS2 + FastAPI hybrid)"

# Source ROS2 Humble setup
source /opt/ros/humble/setup.bash

# Source built hermes_msgs workspace
if [ -f /opt/hermes_ws/install/setup.bash ]; then
    source /opt/hermes_ws/install/setup.bash
    echo "  ROS2 hermes_msgs sourced"
else
    echo "  WARNING: hermes_msgs workspace not found"
fi

# Run initialization script (only runs once)
if [ -x /app/scripts/init_odoo_once.sh ]; then
    /app/scripts/init_odoo_once.sh || echo "  Initialization had issues, continuing anyway..."
fi

# Execute the main application
exec "$@"
