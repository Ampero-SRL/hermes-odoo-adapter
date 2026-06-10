cmake_minimum_required(VERSION 3.5)
project(hermes_msgs)

find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(sensor_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  # Actions
  "action/DockTo.action"
  "action/RequestTray.action"
  "action/ReturnTray.action"
  # Messages
  "msg/GestureCommand.msg"
  "msg/InventoryUpdate.msg"
  "msg/DetectedComponent.msg"
  # Services (process control)
  "srv/ProcessControl.srv"
  # Services (warehouse operations — Adapter v2.0)
  "srv/WarehousePick.srv"
  "srv/WarehousePickStatus.srv"
  "srv/WarehousePickCancel.srv"
  # Services (stock operations — Adapter v2.0)
  "srv/ConsumeStock.srv"
  "srv/ProduceStock.srv"
  # Services (article management — Adapter v2.0)
  "srv/PushArticle.srv"
  # Services (vision — Component Detection)
  "srv/DetectComponents.srv"
  "srv/CalibrateVision.srv"
  # Services (cobot orchestration)
  "srv/CobotPickPlace.srv"
  DEPENDENCIES geometry_msgs builtin_interfaces sensor_msgs
)

ament_package()
