# HERMES Odoo Adapter — sequence diagrams

Three flows the adapter mediates. Mermaid renders inline on GitHub.

## Flow 1 — Project → Shortage (default mock data)

This is the path the in-repo demo exercises by default (see
[`../docs/04_basic_demo_how_to_use.md`](../docs/04_basic_demo_how_to_use.md)).
The mock seed is intentionally short on `WAGO-221-412` so the
adapter takes the shortage branch.

```mermaid
sequenceDiagram
    participant Op as Operator / planner
    participant Orion as Orion-LD
    participant Adapter as Adapter (FastAPI + rclpy)
    participant Odoo as Odoo (mock)

    Op->>Orion: POST Project "demo-ctrl-1" {code: DEMO-CTRL}
    Orion-->>Op: 201 Created
    Orion->>Adapter: POST /orion/notifications (Project)
    Adapter->>Adapter: Project status -> "processing"
    Adapter->>Odoo: read BOM(CTRL-PANEL-A1)
    Odoo-->>Adapter: BOM lines + on-hand stock
    Adapter->>Adapter: BOM not satisfiable (WAGO-221-412 short)
    Adapter->>Orion: PATCH Project.status = "shortage"
    Adapter->>Orion: POST Shortage "demo-ctrl-1" + lines
```

## Flow 2 — top up stock → Reservation

After the operator (or a maintenance job) tops up the short SKU, the
recompute endpoint re-runs the BOM resolution.

```mermaid
sequenceDiagram
    participant Op as Operator
    participant OdMock as Odoo mock
    participant Adapter as Adapter
    participant Odoo as Odoo (mock)
    participant Orion as Orion-LD

    Op->>OdMock: POST /debug/stock/5?quantity=20  (WAGO-221-412)
    OdMock-->>Op: stock updated
    Op->>Adapter: POST /admin/recompute/demo-ctrl-1 {projectCode: DEMO-CTRL}
    Adapter-->>Op: 200 (recompute queued)
    Adapter->>Odoo: re-read BOM + stock
    Odoo-->>Adapter: BOM fully satisfiable
    Adapter->>Orion: PATCH Project.status = "processing" (Reservation done)
    Adapter->>Orion: POST Reservation "demo-ctrl-1" + lines
```

## Flow 3 — Mission Controller pick → ConsumeStock

This is the steady-state DDS-side conversation the adapter is built for
(see [`../docs/04_basic_demo_how_to_use.md`](../docs/04_basic_demo_how_to_use.md)).

```mermaid
sequenceDiagram
    participant MC as Mission Controller
    participant Adapter as Adapter (rclpy)
    participant Wh as WarehouseClient<br/>(Null / Hanel)
    participant Odoo as Odoo
    participant Orion as Orion-LD

    MC->>Adapter: srv /hermes/warehouse/pick (sku, qty)
    Adapter->>Wh: send_pick_order(job_id, sku, qty)
    Wh-->>Adapter: {success, job_id}
    Adapter-->>MC: success, job_id="J-1a2b3c4d"
    MC->>Adapter: srv /hermes/warehouse/status (job_id)
    Adapter->>Wh: get_pick_status(job_id)
    Wh-->>Adapter: {status, slot, tray_ready}
    Adapter-->>MC: status="ready", slot="NULL-A1", tray_ready=true
    MC->>Adapter: srv /hermes/stock/consume (project_id, sku, qty)
    Adapter->>Odoo: stock_move (decrement)
    Odoo-->>Adapter: {remaining_qty}
    Adapter->>Orion: PATCH InventoryItem.available
    Adapter->>MC: pub /hermes/inventory_updates (sku, delta)
    Adapter-->>MC: success, remaining=11.0
```

## Flow 4 — ROS4HRI Intent publish

The adapter fires an `hri_actions_msgs/Intent` on the canonical `/intents`
topic for every Odoo MO event the planner ingests. The Intent fires
immediately after the BOM is retrieved, before stock checking (so a
Shortage in the BOM doesn't suppress the Intent — the planner's *ask*
still happened):

```mermaid
sequenceDiagram
    participant Op as Planner / operator
    participant Orion as Orion-LD
    participant Adapter as Adapter (FastAPI + rclpy)
    participant Odoo as Odoo
    participant Intents as /intents subscribers<br/>(ROS4HRI-aware controllers)

    Op->>Orion: POST Project DEMO-CTRL
    Orion->>Adapter: POST /orion/notifications
    Adapter->>Odoo: read BOM(CTRL-PANEL-A1)
    Odoo-->>Adapter: BOM lines
    Adapter->>Intents: hri_actions_msgs/Intent on /intents<br/>{intent: START_ACTIVITY,<br/>source: erp/odoo,<br/>modality: MODALITY_OTHER,<br/>data: {activity: manufacturing_order,<br/>goal: fulfill_kit, object.id, project_id, bom}}
    Adapter->>Adapter: stock check → Shortage / Reservation
```

Captured wire evidence:
[`../media/screenshots/05_intent_published.log`](../media/screenshots/05_intent_published.log).
