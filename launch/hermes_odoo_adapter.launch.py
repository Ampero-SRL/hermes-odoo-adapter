"""ROS 2 launch wrapper for the HERMES Odoo Adapter.

The adapter is a Python (Poetry / FastAPI + `rclpy`) process — not an
ament package — so this launch file is a thin `ExecuteProcess` wrapper
that lets the standard `ros2 launch` entrypoint start it the same way
the Docker entrypoint does (`python -m hermes_odoo_adapter`).

Because the adapter isn't installed as an ament package, **invoke the
launch file by path**, not by package name:

    # Native (ROS 2 Humble + Vulcanexus already sourced):
    ros2 launch ./launch/hermes_odoo_adapter.launch.py

    # Inside the demo Docker image (launch/ is copied to /app/launch/):
    docker compose exec adapter \\
        ros2 launch /app/launch/hermes_odoo_adapter.launch.py

Launch arguments:

    ros2_node_name      override the rclpy node name (default: hermes_adapter)
    warehouse_backend   null | hanel_hostcom | hanel_soap (default: null)
    log_level           debug | info | warning | error    (default: info)

All other adapter knobs come from the process environment (see
`.env.example`); set them before invoking `ros2 launch` (or via
`docker compose` env_file / environment blocks).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import EnvironmentVariable, LaunchConfiguration


def generate_launch_description() -> LaunchDescription:
    ros2_node_name = LaunchConfiguration("ros2_node_name")
    warehouse_backend = LaunchConfiguration("warehouse_backend")
    log_level = LaunchConfiguration("log_level")

    adapter_process = ExecuteProcess(
        cmd=["python3", "-m", "hermes_odoo_adapter"],
        name="hermes_odoo_adapter",
        output="screen",
        additional_env={
            "ROS2_NODE_NAME": ros2_node_name,
            "WAREHOUSE_BACKEND": warehouse_backend,
            "LOG_LEVEL": log_level,
            "ROS_DOMAIN_ID": EnvironmentVariable("ROS_DOMAIN_ID", default_value="42"),
        },
        respawn=False,
        emulate_tty=True,
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "ros2_node_name",
                default_value="hermes_adapter",
                description="rclpy node name (override of settings.ros2_node_name).",
            ),
            DeclareLaunchArgument(
                "warehouse_backend",
                default_value="null",
                description="Which WarehouseClient backend to instantiate "
                "(null / hanel_hostcom / hanel_soap).",
            ),
            DeclareLaunchArgument(
                "log_level",
                default_value="info",
                description="Adapter log level (debug / info / warning / error).",
            ),
            adapter_process,
        ]
    )
