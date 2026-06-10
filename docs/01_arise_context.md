# 01 — ARISE context

> **Audience:** ARISE reviewer or third-party robotics integrator.
> **Reading time:** 5 minutes.
> **Pre-requisites:** none.

## What this module is

The **HERMES Odoo Adapter** is a single Python process that bridges four
industrial protocols used in a mixed-robotics assembly cell:

```
   ROS 2 / Vulcanexus (DDS)            HTTP REST (FastAPI / NGSI-LD)
            │                                       │
            └────────────┬────────────┬─────────────┘
                         │            │
              ┌──────────▼────────────▼──────────┐
              │      HERMES Odoo Adapter         │
              │   (rclpy + FastAPI in one proc)  │
              └──────────┬────────────┬──────────┘
                         │            │
                JSON-RPC │            │ HOST-COM (raw TCP) — default
                         │            │ HOST-WEB SOAP 1.1 — legacy
                         ▼            ▼
                 ┌────────────┐  ┌────────────────┐
                 │  Odoo ERP  │  │  Hänel ASRS    │
                 └────────────┘  └────────────────┘
```

- **DDS face**: ROS 2 services and topics used by an upstream Mission
  Controller to request tray retrieval, consume/produce stock, and stream
  inventory updates.
- **HTTP / NGSI-LD face**: FastAPI endpoints for health, metrics, and
  Orion-LD subscription callbacks. The adapter owns four NGSI-LD entity
  types — `Project`, `Reservation`, `Shortage`, `InventoryItem` — and keeps
  them in sync with the Odoo source of truth.
- **JSON-RPC (Odoo)**: BOM resolution, manufacturing-order polling, stock
  moves.
- **Hänel HOST-COM (raw TCP telegrams, port 2200)**: tray retrieval and
  inventory reconciliation against the vertical lift. This is the default
  production backend (`HanelHostComClient`). A legacy **HOST-WEB SOAP 1.1**
  backend (`HanelSoapClient`, against `http://<IP>/ws/com?wsdl`) is also
  kept for Hänel installations that expose the SOAP/JWS interface only.

## Why the module exists

A generic robotics cell talks ROS 2; a real factory's planning system talks
ERP (JSON-RPC or OPC UA); a vertical-lift warehouse talks a vendor-specific
protocol (Hänel HOST-COM, here); an operator-facing digital twin talks
NGSI-LD. Each integration is small in isolation but the **composition** is
non-trivial because:

- Manufacturing orders flow from the planner to the cell — but a Mission
  Controller wants a clean DDS service interface, not a JSON-RPC poll loop.
- Stock has to stay consistent across the ERP, the warehouse controller,
  and the FIWARE digital twin, with sub-second NGSI-LD updates so the
  HoloLens AR operator app sees the right state.
- Errors in any link (Hänel offline, Odoo timeout, NGSI-LD broker slow) must
  be observable but must not block the robotics pipeline.

The adapter is the **single process** that owns those compositions, so the
Mission Controller and the operator-facing apps stay simple.

## ARISE alignment

| ARISE concept | How the adapter contributes |
|---|---|
| **Vulcanexus / ROS 2** | Built on `eprosima/vulcanexus:humble`. The adapter is a `rclpy.Node` hosted in a background thread inside a FastAPI process — a reusable pattern for embedding ERP/FIWARE bridges in a Vulcanexus container. Default ROS 2 QoS, `ROS_DOMAIN_ID=42`, Fast-DDS as the transport. |
| **FIWARE / NGSI-LD** | Talks NGSI-LD natively to Orion-LD. Owns four canonical entity types (`Project`, `Reservation`, `Shortage`, `InventoryItem`) with public JSON Schemas and a project-specific `@context` — see [`contracts/`](../contracts/). |
| **DDS NGSI-LD integration** | The FIWARE DDS Enabler is **N/A** for this module: the bridging is performed in-process in `ros2_node.py` ↔ `orion_client.py`. The canonical topic ↔ entity mapping is documented in [`config/README.md`](../config/README.md) so a third party can swap in the enabler if they want. |
| **ROS4HRI / ROS4RI** | **Used — mapped, publisher implementation pending (Sprint 0.4).** The adapter will publish `hri_actions_msgs/Intent` for the **Odoo planner manufacturing-order intent** (`intent=START_ACTIVITY`, `source=REMOTE_SUPERVISOR`, `modality=MODALITY_OTHER`); operator-side intents from the HoloLens AR app live in companion ROS 2 nodes closer to the source. The mapping table is locked — see [`02_interfaces.md`](02_interfaces.md) §4. The publisher itself is not yet in `ros2_node.py`. |

## Role in the HERMES TRL6-7 demonstrator

The demonstrator is a custom electrical-panel assembly cell with:

- 2× JAKA Pro 16 cobots (ASRS picking + assembly handover).
- A Hänel MP 12N vertical lift (component storage).
- An XBOT wireless AGV (component shuttling between cells).
- A Basler 4K USB3 camera on a Jetson Orin (Vulcanexus + DINOv2 detection).
- A HoloLens AR operator app for project selection and wiring guidance.
- An Odoo 17 ERP holding the customer orders and BOMs.

The adapter is the integration backbone: customer orders enter via Odoo,
fan out as NGSI-LD entities, get translated into ROS 2 service calls for
the Mission Controller, drive the Hänel HOST-COM telegrams that bring trays
to the pickup point, and stream stock changes back to the digital twin.

For a step-by-step walkthrough of where the adapter sits in the
demonstrator pipeline, see [`05_role_in_demonstrator.md`](05_role_in_demonstrator.md).

## What the adapter is **not**

- Not a Mission Controller — it does not plan or sequence robot motions.
- Not a perception / detection module — it consumes `/hermes/inventory_updates`
  but does not detect components itself.
- Not a generic ERP middleware — it speaks Odoo's JSON-RPC dialect specifically
  (extending to other ERPs is a clean `OdooClient` reimplementation, ~500 LOC).
- Not a hardware abstraction layer for the warehouse — only Hänel is
  implemented today (`HanelHostComClient` for raw TCP HOST-COM, default;
  `HanelSoapClient` for legacy HOST-WEB SOAP). The `WarehouseClient` ABC
  in [`src/hermes_odoo_adapter/warehouse/`](../src/hermes_odoo_adapter/warehouse/)
  is the reimplement-here-for-your-vendor seam.

## Next reading

- [`02_interfaces.md`](02_interfaces.md) — the canonical interface reference (ROS 2, FIWARE, DDS, ROS4HRI).
- [`03_installation_and_hello_world.md`](03_installation_and_hello_world.md) — clone-to-output in five commands.
- [`04_basic_demo_how_to_use.md`](04_basic_demo_how_to_use.md) — end-to-end Odoo → Orion → ROS 2 → mock-cobot walkthrough.
- [`05_role_in_demonstrator.md`](05_role_in_demonstrator.md) — how this module slots into the full HERMES TRL6-7 demonstrator.
- [`D4_REPORT_DRAFT.md`](D4_REPORT_DRAFT.md) — the ARISE D4 written-report working draft.
- [`D4_PLAN.md`](D4_PLAN.md) — internal task plan for the D4 submission.
