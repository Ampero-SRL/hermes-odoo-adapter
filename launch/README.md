# `launch/`

ROS 2 launch entrypoints for the adapter.

The HERMES Odoo Adapter is a Python (Poetry / FastAPI + `rclpy`)
process, not an ament package. The launch file here is a thin
`ExecuteProcess` wrapper that runs `python -m hermes_odoo_adapter` —
the same command the Docker entrypoint runs — so a user who has the
adapter source tree can drive it through the standard ROS 2 launch
system.

> **Two invocation forms** (pick whichever fits your workflow):
>
> 1. **Path-based** (no extra ament install needed): `ros2 launch
>    ./launch/hermes_odoo_adapter.launch.py`. Works straight from the
>    repo root.
> 2. **Package-name based** (after a colcon build of the small
>    `hermes_odoo_adapter_launch` ament wrapper at
>    [`../ros2_ws/src/hermes_odoo_adapter_launch/`](../ros2_ws/src/hermes_odoo_adapter_launch/)):
>    `ros2 launch hermes_odoo_adapter_launch hermes_odoo_adapter.launch.py`.
>    The Dockerfile builds the wrapper automatically; for a native
>    install, run `cd ros2_ws && colcon build --packages-select
>    hermes_odoo_adapter_launch hri_actions_msgs hermes_msgs && source
>    install/setup.bash` first.

## `hermes_odoo_adapter.launch.py`

Native invocation (ROS 2 Humble / Vulcanexus already sourced, vendored
`hermes_msgs` already built in your workspace, **demo compose NOT
running on the same host** — both would bind `:8080` and the same
`ROS_DOMAIN_ID`):

```bash
ros2 launch ./launch/hermes_odoo_adapter.launch.py
```

> **Why no `docker compose exec` example?** The demo compose
> (`docker/docker-compose.demo.yml`) already starts the adapter via
> the Dockerfile `CMD` (`python -m hermes_odoo_adapter`). Running
> `ros2 launch` inside the same container would try to start a
> second copy that conflicts on port 8080 + ROS topic names.
> `launch/` is copied to `/app/launch/` mainly so the file can be
> inspected from inside the container; if you want to drive the
> adapter via `ros2 launch` instead of the Dockerfile CMD, stop the
> compose service first and re-run from a sourced ROS 2 shell.

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
