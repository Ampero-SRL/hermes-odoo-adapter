# 02 — Interfaces

> **Audience:** integrators wiring the adapter into a robotics cell or a
> FIWARE deployment. ARISE D4 §3.2.6 evidence page.
> **Reading time:** 15 minutes.

The adapter exposes four interfaces:

| # | Interface | Protocol | Faced by |
|---|---|---|---|
| 1 | **ROS 2 / Vulcanexus** | DDS (Fast-DDS) | Mission Controller, robotics nodes |
| 2 | **FIWARE / NGSI-LD** | HTTP REST against Orion-LD | Digital-twin dashboards, HoloLens AR app, planner UIs |
| 3 | **Local HTTP / FastAPI** | HTTP REST | Health, metrics, webhooks, admin |
| 4 | **ROS4HRI Intent** | DDS (Fast-DDS) | Any ROS4HRI-aware consumer |

Outbound, the adapter also talks **Odoo JSON-RPC** and the **Hänel**
warehouse — by default through `HanelHostComClient` (raw TCP HOST-COM
telegrams, port 2200), with a legacy `HanelSoapClient` (HOST-WEB SOAP 1.1
against `/ws/com?wsdl`) selectable via the `WAREHOUSE_BACKEND` env var.
Those are integration outputs, not part of the published interface
contract.

---

## 1. ROS 2 / Vulcanexus

Node name: `hermes_adapter` (the default of `settings.ros2_node_name`;
the `ROS2_NODE_NAME` env var overrides it). The node runs in a
background thread inside the FastAPI process, so the adapter is a
single container with a single DDS participant.

### Services

| Service | Type | Direction | Request | Response | Purpose |
|---|---|---|---|---|---|
| `/hermes/warehouse/pick` | `hermes_msgs/srv/WarehousePick` | Server | `string job_id, string sku, int32 quantity` | `bool success, string job_id, string error` | Initiate a tray retrieval. Empty `job_id` → the adapter assigns one as `J-<8 hex chars>`. |
| `/hermes/warehouse/status` | `hermes_msgs/srv/WarehousePickStatus` | Server | `string job_id` | `string status, string slot, bool tray_ready` | Poll a pick job. `status` is one of `submitted` / `presenting` / `ready` / `failed`; `slot` is e.g. `L1-S7` (Hänel) or `NULL-A1` (mock). |
| `/hermes/warehouse/cancel` | `hermes_msgs/srv/WarehousePickCancel` | Server | `string job_id` | `bool success` | Cancel an in-flight retrieval. |
| `/hermes/stock/consume` | `hermes_msgs/srv/ConsumeStock` | Server | `string project_id, string sku, int32 quantity` | `bool success, float64 remaining` | Decrement Odoo stock + PATCH the matching `InventoryItem` after a cobot pick + publish on `/hermes/inventory_updates`. |
| `/hermes/stock/produce` | `hermes_msgs/srv/ProduceStock` | Server | `string project_id, string sku, int32 quantity` | `bool success` | Increment finished-product stock at end of assembly. |

The `.srv` definitions live in the vendored `ros2_ws/src/hermes_msgs/`
package (see `VENDORED_FROM.md` there).

### Topics

| Topic | Type | Direction | QoS | Purpose |
|---|---|---|---|---|
| `/hermes/inventory_updates` | `hermes_msgs/msg/InventoryUpdate` | **Publish** | default (KEEP_LAST/10) | Stock-change events emitted by the adapter. |
| `/hermes/warehouse/tray_state` | `std_msgs/Int16` | **Publish** | latched: `KEEP_LAST/1` + `TRANSIENT_LOCAL` (reliability inherited from default) | Current tray id at the Hänel pickup point; latched so late joiners see the last value. |
| `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | **Publish** | default | Per-subsystem health (warehouse / Odoo / Orion / ROS 2). Published once per second by a timer. |
| `/hermes/mission_state` | `std_msgs/String` (JSON payload) | **Subscribe** | default | Mission-controller state stream — the adapter parses the JSON and applies the relevant NGSI-LD patches. |
| `/humans/intents` *(planned, Sprint 0.4)* | `hri_actions_msgs/Intent` | **Publish** | default | ROS4HRI alignment — see §4 below. The publisher is **not yet implemented** in this adapter; once it lands, this row will lose the *(planned)* tag. |

### Parameters

The adapter does not currently declare ROS 2 parameters; all configuration
flows through environment variables (see `.env.example` and `settings.py`).
Adding `rclpy` parameters for the most-tuned settings (QoS overrides, the
ROS4HRI intent topic name) is on the Sprint 1 backlog.

### Launch

The adapter has three equivalent entrypoints:

| Entrypoint | When to use |
|---|---|
| `python -m hermes_odoo_adapter` | Local dev (host has ROS 2 + Vulcanexus + vendored `hermes_msgs` built). |
| `docker compose -f docker/docker-compose.demo.yml up` | Fresh-clone hello world / basic demo. |
| `ros2 launch hermes_odoo_adapter hermes_odoo_adapter.launch.py` | Standard ROS 2 launch system (declares `ros2_node_name` / `warehouse_backend` / `log_level` / `extra_env` arguments). See [`../launch/`](../launch/). |

### Service usage examples

```bash
# In a Vulcanexus / ROS 2 Humble shell with the adapter running.

# 1) Request a warehouse pick. Empty job_id → server assigns one as J-<8 hex>.
ros2 service call /hermes/warehouse/pick hermes_msgs/srv/WarehousePick \
  "{job_id: '', sku: 'SCH-REL-24V', quantity: 10}"
# -> response: hermes_msgs.srv.WarehousePick_Response(
#       success=True, job_id='J-1a2b3c4d', error='')

# 2) Poll the pick status. Slot for NullWarehouseClient is 'NULL-A1'.
ros2 service call /hermes/warehouse/status hermes_msgs/srv/WarehousePickStatus \
  "{job_id: 'J-1a2b3c4d'}"
# -> response: hermes_msgs.srv.WarehousePickStatus_Response(
#       status='ready', slot='NULL-A1', tray_ready=True)

# 3) After the cobot picks, decrement stock. Note the .srv has no
#    `operator` field — only project_id / sku / quantity.
ros2 service call /hermes/stock/consume hermes_msgs/srv/ConsumeStock \
  "{project_id: 'urn:ngsi-ld:Project:demo-ctrl-1', sku: 'SCH-REL-24V', quantity: 1}"
# -> response: hermes_msgs.srv.ConsumeStock_Response(
#       success=True, remaining=11.0)
```

More command samples live in [`examples/ros2/`](../examples/ros2/).

---

## 2. FIWARE / NGSI-LD

### Entity types managed

The adapter owns four NGSI-LD entity types end-to-end (CREATE / PATCH /
GET) against an Orion-LD broker:

| Entity type | Purpose | Schema | Owner |
|---|---|---|---|
| `Project` | A manufacturing job derived from an Odoo MO. Carries `code`, `station`, `status` (enum: `requested` / `ready` / `blocked` / `running` / `completed` / `cancelled`). | [`contracts/schemas/Project.schema.json`](../contracts/schemas/Project.schema.json) | Mission Controller (or HoloLens AR app) creates; adapter PATCHes `status` as the assembly progresses. |
| `Reservation` | The BOM-line reservation for a `Project` — what components have to be picked. | [`contracts/schemas/Reservation.schema.json`](../contracts/schemas/Reservation.schema.json) | Adapter creates / patches. |
| `Shortage` | A reservation line that cannot be satisfied from stock right now. | [`contracts/schemas/Shortage.schema.json`](../contracts/schemas/Shortage.schema.json) | Adapter creates. |
| `InventoryItem` | Current stock level of a SKU. | [`contracts/schemas/InventoryItem.schema.json`](../contracts/schemas/InventoryItem.schema.json) | Adapter syncs from Odoo + warehouse. |

The `@context` is at [`contracts/context/context.jsonld`](../contracts/context/context.jsonld)
and is also served by the adapter at `GET /context.jsonld` for any consumer
that wants to fetch it directly from the running instance.

### Sample payload — `InventoryItem`

The schema splits stock across three properties — `available`, `reserved`
and `total` — so consumers can subscribe to a single property if they
want partial updates. `total = available + reserved`.

```json
{
  "id": "urn:ngsi-ld:InventoryItem:SCH-REL-24V",
  "type": "InventoryItem",
  "sku":       {"type": "Property", "value": "SCH-REL-24V"},
  "available": {"type": "Property", "value": 12, "unitCode": "Unit"},
  "reserved":  {"type": "Property", "value": 0,  "unitCode": "Unit"},
  "total":     {"type": "Property", "value": 12, "unitCode": "Unit"},
  "updatedAt": {"type": "Property", "value": "2026-05-27T15:42:00Z"},
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "http://localhost:8080/context.jsonld"
  ]
}
```

A `Reservation` carries the BOM lines as a structured value — an array
of `{sku, qty, unit}` objects, **not** a JSON-encoded string:

```json
"lines": {
  "type": "Property",
  "value": [
    {"sku": "SCH-REL-24V", "qty": 1, "unit": "Unit"},
    {"sku": "ABB-MCB-10A", "qty": 2, "unit": "Unit"}
  ]
}
```

A `Shortage` is one entity *per project* (`urn:ngsi-ld:Shortage:{project}`),
with a `lines` value listing every short SKU and its `missingQty` /
`requiredQty` / `availableQty`. See [`examples/payloads/`](../examples/payloads/)
for canonical samples of each entity.

See [`examples/payloads/`](../examples/payloads/) for a sample per entity type.

### Broker subscriptions

The adapter accepts NGSI-LD subscriptions from Orion-LD on its own
HTTP face. Typical flow:

1. The Mission Controller (or any third party) creates a `Project` entity
   in Orion-LD.
2. Orion-LD POSTs a subscription notification to the adapter at
   `POST /orion/notifications`.
3. The adapter resolves the Odoo MO behind that `Project`, materialises
   the `Reservation` + any `Shortage`, and PATCHes the `Project` status.

### Broker configuration

Set via environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `ORION_URL` | `http://orion-ld:1026` | NGSI-LD endpoint. |
| `ORION_TENANT` | *(unset)* | Optional `NGSILD-Tenant` header. |
| `CONTEXT_URL` | `http://localhost:8080/context.jsonld` | The `@context` URL the adapter advertises in payloads. |

---

## 3. Local HTTP / FastAPI

The HTTP face is mainly for **operations** (health, metrics, webhooks) and
for the **admin / debug** surface during integration.

| Endpoint | Method | Purpose |
|---|---|---|
| `/healthz` | GET | Liveness probe — always responds if the process is alive. |
| `/readyz` | GET | Readiness probe — checks Odoo + Orion + warehouse subsystem health. |
| `/metrics` | GET | Prometheus `text/plain` metrics. |
| `/context.jsonld` | GET | The adapter's NGSI-LD `@context`. |
| `/orion/notifications` | POST | Receives Orion-LD subscription notifications. |
| `/odoo/webhook` | POST | (Optional) receives Odoo state changes for low-latency sync. |
| `/api/consume` | POST | HTTP wrapper around the `ConsumeStock` ROS 2 service for clients that aren't on ROS 2. |
| `/api/produce` | POST | HTTP wrapper around `ProduceStock`. |
| `/admin/recompute/{project_id}` | POST | Force-recompute a Project's reservation. |
| `/admin/inventory/sync` | GET | Trigger a full Odoo → Orion inventory sync. |
| `/admin/inventory/status` | GET | Snapshot of the inventory sync worker state. |
| `/admin/inventory/sync/{sku}` | POST | Sync a single SKU. |
| `/admin/idempotency/{project_id}` | DELETE | Clear the idempotency cache for a project (rare; debugging). |
| `/admin/idempotency` | DELETE | Clear all idempotency entries. |
| `/debug/reservation/{project_id}` | GET | Read-only inspection of a reservation (when `DEBUG_ENDPOINTS=true`). |

---

## 4. ROS4HRI / ROS4RI Intent

### Position: **Used — mapped, publisher implementation pending (Sprint 0.4)**

The adapter will publish [`hri_actions_msgs/Intent`](https://github.com/ros4hri/hri_actions_msgs/blob/humble-devel/msg/Intent.msg)
for the human-originated inputs **it directly ingests** — which in this
repo means **only the Odoo planner manufacturing-order intent**.
Operator-side intents (HoloLens project-selection, placement confirmation,
assembly-complete) live in companion ROS 2 nodes closer to their source
(`hermes_main/ar_bridge_node`, a future companion next to
`hermes_main/hololens_api`) and are mapped in [`D4_PLAN.md`](D4_PLAN.md) §4.4.
The adapter re-uses the standard `Intent.intent` constants where they
fit and adds domain-specific labels where they don't. **No message extension** — the
`hri_actions_msgs/Intent` envelope is used as-is, with a free-form
`intent` string and a JSON `data` payload for the thematic roles.

> **Implementation status.** The mapping below is the canonical plan;
> the actual publisher code is **not yet in `ros2_node.py`** as of the D4
> Sprint 1 cut. The mapping table is locked, but a few mentor questions
> (canonical topic name, custom-label acceptance) are still open — see
> [`D4_PLAN.md`](D4_PLAN.md) §4.4. Sprint 0.4 lands the implementation;
> until then this section documents the contract the adapter targets,
> not what it emits today.

### Intent topology

ROS4HRI guidance is to publish the `Intent` **as close to the source as
possible**, so the publisher topology is split:

| Source of the human intent | Publisher node | Repo |
|---|---|---|
| HoloLens "Confirm placement" (AR-button) | `ar_bridge_node` (already a ROS 2 node, receives the placement HTTP) | `hermes_main/` |
| HoloLens "Select project" / "Assembly complete" | new companion node next to `hololens_api` (or extend `ar_bridge_node` to take both) | `hermes_main/` |
| **Odoo planner creates a manufacturing order** | **this adapter** — the only flow the adapter directly ingests | **this repo** |

Only the **Odoo MO intent** is published from this repo, on
`/humans/intents` (the topic name is configurable; the placeholder is
`/humans/intents` until the ARISE ROS4HRI mentor confirms the canonical
choice).

### Mapping table (this adapter — the Odoo MO intent only)

| Adapter event | `Intent.intent` | `Intent.source` | `Intent.modality` | `Intent.data` (JSON) | Mapping kind |
|---|---|---|---|---|---|
| Odoo planner places a manufacturing order (adapter polls Odoo → creates `Reservation` in Orion-LD) | `START_ACTIVITY` (standard constant) or domain `FULFILL_KIT` | `REMOTE_SUPERVISOR` (standard) or `UNKNOWN_AGENT` if no Odoo user attribution | `MODALITY_OTHER` (standard) — best fit for an ERP-form-submission modality | `{"activity":"manufacturing_order","mo_id":"...","bom":[{"sku":"...","qty":...}, ...],"project_id":"urn:ngsi-ld:Project:..."}` | **Used — standard constant + domain JSON payload** |

For the **other** human-originated intents (HoloLens flows handled by
companion nodes), see [`D4_PLAN.md`](D4_PLAN.md) §4.4 for the full mapping
table. Codex-validated narrowing: only `START_ACTIVITY` cleanly fits a
standard `Intent.intent` constant; `PLACE_OBJECT` / `STOP_ACTIVITY` would
over-claim semantic equivalence (their upstream semantics are about
commanding the robot or cancelling, not the operator confirming /
completing). Domain labels `CONFIRM_PLACEMENT` and `COMPLETE_ACTIVITY` are
used for those two flows instead.

### Dependency

`hri_actions_msgs` is fetched via [`ros2_ws/deps.repos`](../ros2_ws/deps.repos)
when an apt package isn't available on the target Vulcanexus / Humble
distribution. The Dockerfile build will be extended in Sprint 0.4 to run
`vcs import` + `colcon build` for `hri_actions_msgs` alongside the
vendored `hermes_msgs`.

### Why not the FIWARE DDS Enabler?

See [`config/README.md`](../config/README.md) — `N/A` with the canonical
topic ↔ entity mapping table for any third party that wants to plug the
enabler in front of the adapter.

---

## QoS & DDS configuration

No custom QoS profile is shipped today; the adapter inherits the default
ROS 2 profiles from the Vulcanexus base image. Notable explicit choice:

- `/hermes/warehouse/tray_state` is **latched** (KEEP_LAST/1, TRANSIENT_LOCAL,
  RELIABLE) so a late-joining consumer sees the current tray immediately.

A custom XML profile would live at `config/fastdds_profile.xml`. Adding
one for cross-network deployments (Discovery Server / Easy Mode) is a
documented future-work item.

---

## Quick reference

- All `.srv` / `.msg` definitions: `ros2_ws/src/hermes_msgs/{srv,msg}/`.
- NGSI-LD schemas + `@context`: `contracts/`.
- HTTP route definitions: `src/hermes_odoo_adapter/main.py`.
- ROS 2 node definitions: `src/hermes_odoo_adapter/ros2_node.py`.
- Settings: `src/hermes_odoo_adapter/settings.py` + `.env.example`.
