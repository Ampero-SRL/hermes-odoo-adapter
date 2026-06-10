# `launch/`

ROS 2 launch entrypoints for the adapter.

The HERMES Odoo Adapter is a Python (Poetry / FastAPI + `rclpy`) process,
not an ament package, so the launch file here is a thin
`ExecuteProcess` wrapper that runs `python -m hermes_odoo_adapter` under
`ros2 launch`. The same command the Docker entrypoint runs is now also
reachable from the standard ROS 2 launch system.

## `hermes_odoo_adapter.launch.py`

Native invocation (ROS 2 Humble / Vulcanexus already sourced, vendored
`hermes_msgs` already built):

```bash
ros2 launch hermes_odoo_adapter hermes_odoo_adapter.launch.py
```

Inside the demo Docker stack (no host ROS 2 install needed):

```bash
docker compose -f docker/docker-compose.demo.yml exec adapter \
    bash -lc '
        source /opt/ros/humble/setup.bash &&
        source /opt/hermes_ws/install/setup.bash &&
        ros2 launch /app/launch/hermes_odoo_adapter.launch.py
    '
```

### Launch arguments

| Argument | Default | Purpose |
|---|---|---|
| `ros2_node_name` | `hermes_adapter` | Override the rclpy node name (`ROS2_NODE_NAME` env). |
| `warehouse_backend` | `null` | `null` / `hanel_hostcom` / `hanel_soap` — picks the `WarehouseClient` implementation. |
| `log_level` | `info` | Adapter log level. |
| `extra_env` | *(empty)* | Comma-separated `KEY=VALUE` pairs forwarded as env vars. |

All knobs that aren't exposed as launch arguments come from the process
environment (see [`../.env.example`](../.env.example)).

### Why isn't this an ament package?

The adapter is published as a Poetry-managed Python application
(`pyproject.toml`, not `package.xml`). Wrapping it in a colcon
ros-python package is on the backlog if the ARISE ecosystem starts
expecting `ros2 pkg install hermes-odoo-adapter`; until then the
`ExecuteProcess` wrapper above is the simplest correct integration with
the ROS 2 launch system.
