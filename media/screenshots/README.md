# Captured demo evidence

Text logs captured 2026-06-10 by running a fresh-clone
reproducibility test:

```
git clone https://github.com/Ampero-SRL/hermes-odoo-adapter
cd hermes-odoo-adapter
cp .env.example .env
docker compose -f docker/docker-compose.demo.yml up -d
```

…then exercising the documented demo flow
([`../../docs/04_basic_demo_how_to_use.md`](../../docs/04_basic_demo_how_to_use.md))
and capturing the responses / log lines into the files below. These
plain-text artefacts are easier to inspect / diff / cite than PNG
screenshots and don't depend on any rendering pipeline.

## Files

| File | What it proves |
|---|---|
| [`01_healthz.log`](01_healthz.log) | The adapter's liveness endpoint returns the expected `{status: healthy, service: hermes-odoo-adapter, version: 2.0.0}` shape from a fresh clone. |
| [`02_readyz.log`](02_readyz.log) | All four subsystems (Odoo, Orion-LD, warehouse `null` backend, ROS 2 node `hermes_adapter`) are reachable. |
| [`03_stack_status.log`](03_stack_status.log) | `docker compose ps` output showing the four containers (adapter, mongo, odoo-mock, orion-ld) all `Up`. |
| [`04_adapter_startup.log`](04_adapter_startup.log) | First ~40 lines of the adapter's startup log — proves the Odoo / Orion / WarehouseClient initialisations, the ROS 2 node coming up, **`ROS4HRI Intent publisher up on /intents (hri_actions_msgs.msg.Intent)`** and **`ROS4HRI Intent publisher wired into ProjectSyncWorker`**. |
| [`05_intent_published.log`](05_intent_published.log) | Adapter log lines from the actual end-to-end demo run. Two `Published ROS4HRI Intent: START_ACTIVITY mo=1 project=demo-ctrl-1 source=erp/odoo bom_lines=4` lines (one per recompute), each immediately followed by the corresponding `Shortage` or `Reservation` create + Project status patch. |
| [`06_project_entity.log`](06_project_entity.log) | The `urn:ngsi-ld:Project:demo-ctrl-1` entity after the Shortage flow: status moved from `requested` → `shortage`. |
| [`07_shortage_entity.log`](07_shortage_entity.log) | The `urn:ngsi-ld:Shortage:demo-ctrl-1` entity (default mock data path): `WAGO-221-412` is short 4 of the 6 required (only 2 in stock). |
| [`08_metrics.log`](08_metrics.log) | Adapter `/metrics` Prometheus output — every NGSI-LD operation timing, Odoo call timing, warehouse call counters. Useful for latency / performance evidence. |
| [`09_reservation_entity.log`](09_reservation_entity.log) | The `urn:ngsi-ld:Reservation:demo-ctrl-1` entity after the top-up flow: 4 BOM lines (`SCH-REL-24V` ×4, `ABB-MCB-10A` ×2, `DIN-TERM-2.5` ×8, `WAGO-221-412` ×6) under one Reservation, status `pending`, source `odoo`. |
| [`10_ros2_topics.log`](10_ros2_topics.log) | `ros2 topic list` (best-effort — the ros2 CLI's RPC daemon was flaky inside the test container; the actual topic list is shown definitively in `04_adapter_startup.log`'s "topics:" line). |
| [`11_grafana_system_health.png`](11_grafana_system_health.png) | Grafana "HERMES — System Health" dashboard rendered with live data from the full compose stack (`docker-compose.full.yml` + `--profile monitoring`). Captured via Playwright after ~5 minutes of synthetic traffic. `Service Health` panel shows the `hermes-adapter` job UP + `prometheus` UP; `Inventory Items Synced` shows the real count from the adapter's inventory worker. |
| [`12_grafana_manufacturing_ops.png`](12_grafana_manufacturing_ops.png) | Grafana "HERMES — Manufacturing Operations" dashboard. Same run as #11. |
| [`13_grafana_ros2_dds.png`](13_grafana_ros2_dds.png) | Grafana "HERMES Adapter — ROS 2 / ROS4HRI Activity" dashboard, **live with real data** from the adapter's `/metrics`: ROS4HRI Intents published on `/intents` (18), adapter ROS 2 node up, NGSI-LD Reservations (5) vs Shortages (13) created, plus Orion-LD and Odoo request rates. (Fast-DDS middleware statistics aren't shown — the Fast-DDS statistics backend is incompatible with Vulcanexus Humble's Fast-RTPS 2.5.0; the dashboard instead surfaces the adapter-level ROS 2 / ROS4HRI signals that are genuinely measurable.) |
| [`14_prometheus_targets.png`](14_prometheus_targets.png) | Prometheus targets page — the adapter's metrics endpoint scraped and UP (`hermes-adapter` job + Prometheus self-scrape). |
| [`15_odoo_manufacturing_orders.png`](15_odoo_manufacturing_orders.png) | The ERP source side: real Odoo 16 Manufacturing Orders for the `CTRL-PANEL-A1` (Control Panel A1) kit — `WH/MO/00003` with component status **Available** (fully reserved) and `WH/MO/00004` **Not Available** (short on Wago). The SKUs match the demo dataset (`docker/odoo-mock/`) exactly, so these MOs are the ERP-side twins of the NGSI-LD `Reservation` / `Shortage` entities the adapter creates. |
| [`16_odoo_mo_reserved.png`](16_odoo_mo_reserved.png) | Odoo MO `WH/MO/00003` detail — Components tab, all four BOM components fully **Reserved** (Schneider Relay ×4, ABB Circuit Breaker ×2, DIN Rail Terminal ×8, Wago Connector ×6), Component Status **Available**. The ERP-side reservation that the adapter mirrors into the `urn:ngsi-ld:Reservation:*` entity (cf. [`09_reservation_entity.log`](09_reservation_entity.log)). |
| [`17_odoo_mo_shortage.png`](17_odoo_mo_shortage.png) | Odoo MO `WH/MO/00004` detail — Component Status **Not Available**: SCH/ABB/DIN fully reserved but **Wago Connector reserved only 2 of 6** (8 on hand, one MO already took 6). This is the exact same shortage the adapter writes to `urn:ngsi-ld:Shortage:*` — Wago short 4 of 6 (cf. [`07_shortage_entity.log`](07_shortage_entity.log)). |
| [`18_odoo_bom.png`](18_odoo_bom.png) | The `CTRL-PANEL-A1` Bill of Materials in Odoo — the four-component kit (Schneider Relay 24V ×4, ABB Circuit Breaker 10A ×2, DIN Rail Terminal ×8, Wago Connector ×6) the adapter reads (`mrp.bom` → `mrp.bom.line`) to build the reservation/shortage line items. |
| [`19_ros2_intent_echo.log`](19_ros2_intent_echo.log) | `ros2 topic echo /intents` — the **live ROS4HRI Intent message** on the wire: `intent: __intent_start_activity__`, `source: erp/odoo`, `modality: __modality_other__`, and the JSON `data` payload carrying the BOM. Captured from the running stack via a recompute. |
| [`20_ros2_interface_node.log`](20_ros2_interface_node.log) | `ros2 interface show hri_actions_msgs/msg/Intent` (proves the adapter publishes the **unmodified upstream message**, with `START_ACTIVITY = __intent_start_activity__`) + `ros2 node info /hermes_adapter` (the node's full DDS graph: `/intents` publisher + the 5 warehouse/stock service servers). |
| [`21_ngsi_subscription.log`](21_ngsi_subscription.log) | The NGSI-LD subscription the adapter registers on Orion-LD (`urn:ngsi-ld:Subscription:hermes-project`, `status: active`) — proves the event-driven Project → notification wiring. |
| [`22_adapter_swagger_api.png`](22_adapter_swagger_api.png) | The adapter's auto-generated **OpenAPI / Swagger UI** (`/docs`) — the full documented REST surface grouped by tag: monitoring, webhooks, stock-operations, admin, debug + schemas. |
| [`23_pytest_results.log`](23_pytest_results.log) | Unit test suite run — **112 passed, 18 skipped** (the skips are documented stale tests; see [`../../TESTING.md`](../../TESTING.md)). |
| [`24_latency_metrics.png`](24_latency_metrics.png) | Per-operation latency derived from the Prometheus histograms — Odoo JSON-RPC, Orion NGSI-LD and HTTP API calls, all averaging **< 10 ms** on a single-host demo stack. |

> Rendered PNG exports of the Mermaid architecture + sequence diagrams live in [`../diagrams/`](../diagrams/). The editable sources are [`../architecture_diagram.md`](../architecture_diagram.md) and [`../sequence_diagram.md`](../sequence_diagram.md), which render inline on GitHub.

## Naming conventions

- Two-digit prefix + descriptive `snake_case`.
- `.log` for text captures (`curl`, `docker compose logs`).
- `.png` / `.jpg` for actual UI screenshots / photos.
- Keep file sizes < 1 MB where possible.

## Re-capturing

To re-run the capture script (which is intentionally not a separate
file because it's tightly bound to the demo flow walkthrough in
`docs/04_basic_demo_how_to_use.md`):

1. Start the stack: `docker compose -f docker/docker-compose.demo.yml up -d`.
2. Save each `curl` / `docker compose logs` output (per the file
   descriptions above) into a `media/screenshots/<NN>_<name>.log`
   file. The header line of each file is `# <description> — captured
   <date> from a fresh clone`; keep that convention.
