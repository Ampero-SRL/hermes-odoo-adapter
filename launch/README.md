# `launch/`

ROS 2 launch entrypoints for the adapter.

The HERMES Odoo Adapter is a Python (Poetry / FastAPI + `rclpy`)
process, not an ament package. The launch file here is a thin
`ExecuteProcess` wrapper that runs `python -m hermes_odoo_adapter` —
the same command the Docker entrypoint runs — so a user who has the
adapter source tree can drive it through the standard ROS 2 launch
system.

> **Invoke by path, not by package name.** Because the adapter isn't
> installed as an ament package, `ros2 launch hermes_odoo_adapter
> hermes_odoo_adapter.launch.py` won't resolve. Use the path-based
> form below.

## `hermes_odoo_adapter.launch.py`

Native invocation (ROS 2 Humble / Vulcanexus already sourced, vendored
`hermes_msgs` already built in your workspace):

```bash
ros2 launch ./launch/hermes_odoo_adapter.launch.py
```

Inside the demo Docker stack (`launch/` is copied into the image at
`/app/launch/`):

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

All other knobs (Odoo / Orion / Hänel URLs, credentials, sync timing,
…) come from the process environment — see [`../.env.example`](../.env.example).
Set them in the shell that invokes `ros2 launch`, or via the demo
compose file's `env_file` / `environment` blocks.

### Why isn't this an ament package?

The adapter is published as a Poetry-managed Python application
(`pyproject.toml`, not `package.xml`). Wrapping it in a colcon
`ros-python` package — so `ros2 launch hermes_odoo_adapter
hermes_odoo_adapter.launch.py` resolves by name — is on the backlog if
the ARISE ecosystem starts expecting `ros2 pkg list` to surface the
adapter; until then the path-based invocation above is the simplest
correct integration with the ROS 2 launch system.
