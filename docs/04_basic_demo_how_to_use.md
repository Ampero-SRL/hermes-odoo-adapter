# 04 — Basic demo & how to use

> **Audience:** ARISE reviewer / integrator that completed
> [`03_installation_and_hello_world.md`](03_installation_and_hello_world.md)
> and wants to see the adapter drive an end-to-end pipeline.
> **Reading time:** 10 minutes (commands), 20 minutes (with explanation).
> **Pre-requisites:** the demo stack is up (`docker compose -f docker/docker-compose.demo.yml up -d`).

This page exercises the **full** path the adapter is designed for:

```
Odoo (mock) ─► adapter ─► Orion-LD ─► (operator/Mission Controller)
                  │
                  ├─► ROS 2 services (WarehousePick / ConsumeStock / ...)
                  │       drives the NullWarehouseClient
                  │
                  └─► /hermes/inventory_updates topic (DDS)
```

No real hardware involved — the `NullWarehouseClient` plays the role of
the Hänel ASRS and the `docker/odoo-mock/` container plays Odoo.

## Stage 0 — set the scene

| Container | Role | URL |
|---|---|---|
| `adapter` | The HERMES Odoo Adapter (this repo) | http://localhost:8080 |
| `orion` | Orion-LD context broker | http://localhost:1026 |
| `mongo` | Orion's storage | — |
| `odoo-mock` | Stand-in for an Odoo 17 ERP | http://localhost:8069 |
| `prometheus` *(optional)* | Scrapes the adapter `/metrics` | http://localhost:9090 |
| `grafana` *(optional)* | Dashboards for the above | http://localhost:3000 |

Confirm health before continuing:

```bash
bash examples/curl/01_healthz.sh
# -> {"status":"ok",...}
bash examples/curl/02_readyz.sh
# -> {"ready":true,...}
```

## Stage 1 — operator (or planner) places a manufacturing order

In the real cell this happens in two ways:

1. The **HoloLens AR operator app** lets an operator pick a project from a
   list and confirm "start". The AR side persists the selection and the
   adapter ingests it via NGSI-LD.
2. The **Odoo planner** creates a manufacturing order directly in the
   ERP; the adapter polls Odoo and materialises it as an NGSI-LD
   `Project` + `Reservation`.

In the demo we simulate the first path: post a `Project` directly to
Orion-LD using the sample payload. The adapter receives Orion's
subscription notification on `POST /orion/notifications`, resolves the
BOM via the Odoo mock, and creates a `Reservation` (and any `Shortage`).

```bash
# Create a Project in Orion-LD.
bash examples/curl/03_orion_create_project.sh
# -> HTTP/1.1 201 Created
#    Location: /ngsi-ld/v1/entities/urn:ngsi-ld:Project:demo-project-1

# After 1-2 s, the adapter has materialised the Reservation.
bash examples/curl/04_list_entities.sh Reservation
# -> [
#      {
#        "id": "urn:ngsi-ld:Reservation:demo-project-1",
#        "type": "Reservation",
#        "projectRef": {"type":"Relationship","object":"urn:ngsi-ld:Project:demo-project-1"},
#        "status": {"type":"Property","value":"pending"},
#        "lines": {"type":"Property","value":"[{\"sku\":\"ARTICOLO5\",\"quantity\":1},...]"},
#        ...
#      }
#    ]
```

If the BOM cannot be fully satisfied (the mock data includes a deliberate
gap in some scenarios), there will also be a `Shortage` entity. List
them with `bash examples/curl/04_list_entities.sh Shortage`.

**What this proves.** The HTTP / NGSI-LD face of the adapter is wired,
the Odoo client is reachable, and the BOM-resolution path is functional.

## Stage 2 — Mission Controller requests a warehouse pick

A robotics Mission Controller now needs the first SKU from the BOM. It
calls the ROS 2 service exposed by the adapter:

```bash
docker compose -f docker/docker-compose.demo.yml exec adapter \
    bash -lc '
        source /opt/ros/humble/setup.bash &&
        source /opt/hermes_ws/install/setup.bash &&
        bash /app/examples/ros2/01_warehouse_pick.sh
    '
# response:
#   hermes_msgs.srv.WarehousePick_Response(
#       success=True, job_id='M1717-7a3c1b', error='')
```

Capture the returned `job_id` and poll the status:

```bash
docker compose ... exec adapter bash -lc '
    source /opt/ros/humble/setup.bash &&
    source /opt/hermes_ws/install/setup.bash &&
    JOB_ID="M1717-7a3c1b" bash /app/examples/ros2/02_warehouse_status.sh
'
# response (NullWarehouseClient returns ready quickly):
#   hermes_msgs.srv.WarehousePickStatus_Response(
#       status='ready', slot=0, tray_ready=True, error='')
```

Meanwhile the `/hermes/warehouse/tray_state` topic carries the latched
current tray; you can echo it from inside the container:

```bash
docker compose ... exec adapter bash -lc '
    source /opt/ros/humble/setup.bash &&
    source /opt/hermes_ws/install/setup.bash &&
    timeout 3 ros2 topic echo --once /hermes/warehouse/tray_state
'
# data: <slot_id>
```

**What this proves.** The ROS 2 / DDS face is reachable and the
WarehouseClient abstraction (mocked here, Hänel SOAP in production)
drives the right state transitions.

## Stage 3 — cobot picks → adapter decrements stock

After the (mock) cobot picks the component, the Mission Controller calls
the adapter's stock-decrement service. The adapter:

1. Posts the stock move to the Odoo mock (decrementing the SKU quantity).
2. PATCHes the corresponding `InventoryItem.quantity` in Orion-LD.
3. Publishes an `InventoryUpdate` event on `/hermes/inventory_updates`.

```bash
docker compose ... exec adapter bash -lc '
    source /opt/ros/humble/setup.bash &&
    source /opt/hermes_ws/install/setup.bash &&
    bash /app/examples/ros2/04_stock_consume.sh
'
# response:
#   hermes_msgs.srv.ConsumeStock_Response(success=True, error='')

# Confirm the NGSI-LD side.
bash examples/curl/04_list_entities.sh InventoryItem | \
    jq '.[] | select(.sku.value=="ARTICOLO5") | {sku: .sku.value, qty: .quantity.value}'
# -> {"sku":"ARTICOLO5","qty":11}    (was 12, now 11)
```

Watch the DDS topic in another shell to confirm the publish:

```bash
docker compose ... exec adapter bash -lc '
    source /opt/ros/humble/setup.bash &&
    source /opt/hermes_ws/install/setup.bash &&
    timeout 5 ros2 topic echo --once /hermes/inventory_updates
'
# sku: ARTICOLO5
# quantity_delta: -1
# location: ...
```

**What this proves.** The adapter keeps Odoo, Orion-LD, and the DDS
inventory event stream consistent end-to-end.

## Stage 4 — assembly complete → adapter publishes the produced stock

```bash
docker compose ... exec adapter bash -lc '
    source /opt/ros/humble/setup.bash &&
    source /opt/hermes_ws/install/setup.bash &&
    bash /app/examples/ros2/05_stock_produce.sh
'
# response: ProduceStock_Response(success=True, error='')
```

And patch the `Project.status` to `complete` via the digital twin's
NGSI-LD endpoint (the HoloLens AR app does this in the real system —
here we patch it by hand):

```bash
curl -sS -X PATCH \
    -H "Content-Type: application/json" \
    -H "Link: <http://localhost:8080/context.jsonld>; rel=\"http://www.w3.org/ns/json-ld#context\"; type=\"application/ld+json\"" \
    "http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:Project:demo-project-1/attrs" \
    -d '{"status": {"type":"Property","value":"complete"}}'
```

**What this proves.** The full lifecycle (order placed → tray retrieved
→ component consumed → finished good produced → project closed) is
exercised through the adapter.

## What was actually used

| Adapter surface | Exercised in this demo? | Where to see |
|---|---|---|
| `POST /orion/notifications` | Yes — Stage 1 | adapter logs |
| Odoo JSON-RPC client | Yes — Stage 1, 3, 4 | adapter logs (BOM read + stock moves) |
| `Project` / `Reservation` / `Shortage` / `InventoryItem` entities | Yes | `curl examples/04_list_entities.sh <Type>` |
| ROS 2 `WarehousePick` / `WarehousePickStatus` / `WarehousePickCancel` | Yes — Stage 2 | `examples/ros2/0[1-3]_*.sh` |
| ROS 2 `ConsumeStock` / `ProduceStock` | Yes — Stage 3 + 4 | `examples/ros2/0[4-5]_*.sh` |
| Topic `/hermes/inventory_updates` | Yes — Stage 3 | `ros2 topic echo` |
| Topic `/hermes/warehouse/tray_state` | Yes — Stage 2 | `ros2 topic echo` |
| Topic `/diagnostics` | (continuously) | `ros2 topic echo /diagnostics` |
| Topic `/hermes/mission_state` (subscriber) | **Not exercised** in this demo — needs an upstream Mission Controller publishing it. | n/a |
| ROS4HRI `Intent` publish (Sprint 0.4) | **Not exercised yet** — implementation pending mentor decisions; see [`D4_PLAN.md`](D4_PLAN.md) §4.4. | n/a |

## Tearing down

```bash
docker compose -f docker/docker-compose.demo.yml down -v
```

`-v` removes the Mongo volume so the next run starts clean. Drop it if
you want Orion-LD entities to persist between runs.

## Next reading

- [`05_role_in_demonstrator.md`](05_role_in_demonstrator.md) — same flow at the TRL6-7 demonstrator scale, with the real JAKA + Hänel + AGV + HoloLens.
- [`02_interfaces.md`](02_interfaces.md) — the canonical interface reference if you want to extend the demo with your own client.
