"""ROS 2 launch wrapper for the HERMES Odoo Adapter (ament copy).

This file is a copy of ``../../../../launch/hermes_odoo_adapter.launch.py``
that ships inside the ``hermes_odoo_adapter_launch`` ament_python package
so that the launch file is discoverable by package name:

    ros2 launch hermes_odoo_adapter_launch hermes_odoo_adapter.launch.py

The path-based invocation from the repo root remains the canonical
form for editing / iteration:

    ros2 launch ./launch/hermes_odoo_adapter.launch.py

> **Sync:** if you edit one of these two files, edit the other too —
> the ``hermes_odoo_adapter_launch`` package's README lists this as a
> known maintenance item.
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
                description=(
                    "Which WarehouseClient backend to instantiate "
                    "(null / hanel_hostcom / hanel_soap)."
                ),
            ),
            DeclareLaunchArgument(
                "log_level",
                default_value="info",
                description="Adapter log level (debug / info / warning / error).",
            ),
            adapter_process,
        ]
    )
