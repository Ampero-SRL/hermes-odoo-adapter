# Examples

Minimal runnable inputs that drive the adapter through the demo
Docker Compose stack (`docker/docker-compose.demo.yml`). Each example
includes a one-line description, the command to run, and the expected
output shape so you can tell at a glance whether the adapter is
behaving.

> **Pre-requisites:** the demo stack is running (see
> [`../docs/03_installation_and_hello_world.md`](../docs/03_installation_and_hello_world.md)).

```
examples/
  README.md                          # this file
  payloads/                          # sample NGSI-LD entity payloads
    project.json
    reservation.json
    inventory_item.json
    shortage.json
  curl/                              # HTTP (FastAPI) examples
    01_healthz.sh
    02_readyz.sh
    03_orion_create_project.sh
    04_list_entities.sh
    05_consume_stock.sh
    06_admin_inventory_sync.sh
  ros2/                              # ROS 2 service-call examples
    01_warehouse_pick.sh
    02_warehouse_status.sh
    03_warehouse_cancel.sh
    04_stock_consume.sh
    05_stock_produce.sh
```

Run an HTTP example end-to-end:

```bash
bash examples/curl/01_healthz.sh
```

Run a ROS 2 example (from a Vulcanexus / Humble shell, or via
`docker compose ... exec adapter bash`):

```bash
bash examples/ros2/01_warehouse_pick.sh
```

Each script prints the expected output as a comment at the top so it can
also be used as a documentation reference.
