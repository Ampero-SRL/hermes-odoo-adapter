# `hermes_odoo_adapter_launch`

A tiny `ament_python` package whose only purpose is to make the
adapter's launch file discoverable by ROS 2 package name:

```bash
ros2 launch hermes_odoo_adapter_launch hermes_odoo_adapter.launch.py
```

The adapter itself is a Poetry-managed Python application
(`../../../pyproject.toml`); this package is **not** the adapter — it
only carries the launch file into the `share/` index.

## Building

```bash
cd ros2_ws
colcon build --packages-select hermes_odoo_adapter_launch hri_actions_msgs hermes_msgs
source install/setup.bash
ros2 launch hermes_odoo_adapter_launch hermes_odoo_adapter.launch.py
```

The production Dockerfile colcon-builds this package automatically
alongside `hermes_msgs` and `hri_actions_msgs`.

## Files

| File | Role |
|---|---|
| `package.xml` | ament_python build manifest. |
| `setup.py` + `setup.cfg` | Install the launch file into `share/<pkg>/launch/`. |
| `launch/hermes_odoo_adapter.launch.py` | A **copy** of the top-level [`../../../../launch/hermes_odoo_adapter.launch.py`](../../../../launch/hermes_odoo_adapter.launch.py); ROS 2 expects the file to live under `share/` to be discoverable by package name. |
| `resource/hermes_odoo_adapter_launch` | Empty marker file required by `ament_index`. |
| `hermes_odoo_adapter_launch/__init__.py` | Empty — satisfies setuptools' `packages=[<name>]`. |

## Maintenance

The launch file is duplicated: the canonical edit point is the
top-level [`../../../../launch/hermes_odoo_adapter.launch.py`](../../../../launch/hermes_odoo_adapter.launch.py),
and `launch/hermes_odoo_adapter.launch.py` here must be kept in sync.
If/when the ROS 2 launch system grows a way to expose a relative-path
launch file under the package share without copying (or if we make the
adapter itself an ament package), this duplication goes away.
