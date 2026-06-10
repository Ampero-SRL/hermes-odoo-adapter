# Screenshot inventory

Each screenshot below is referenced from one of the docs/ pages or from
the D4 written report (`docs/D4_REPORT_DRAFT.md`). Capture once with
the demo stack running (`docker compose -f docker/docker-compose.demo.yml up -d`)
and drop the PNG into this directory.

## Required shot list

| File | What to capture | Used in |
|---|---|---|
| `01_healthz.png` | Terminal showing `bash examples/curl/01_healthz.sh` output. | `docs/03_installation_and_hello_world.md` |
| `02_orion_entities.png` | Orion-LD entity browser (or the response to `curl /ngsi-ld/v1/entities?type=Project`) showing the demo Project + Shortage. | `docs/04_basic_demo_how_to_use.md` Stage 1 |
| `03_ros2_topic_graph.png` | `rqt_graph` (or `ros2 topic list`) showing `/hermes/warehouse/tray_state`, `/hermes/inventory_updates`, `/diagnostics`, `/hermes/mission_state`. | `docs/02_interfaces.md` + `docs/05_role_in_demonstrator.md` |
| `04_warehouse_pick_call.png` | `ros2 service call /hermes/warehouse/pick …` response. | `docs/03_installation_and_hello_world.md` (Hello World) |
| `05_grafana_metrics.png` | Optional — Grafana dashboard from the demo stack showing per-NGSI-LD-operation latency and Odoo-call timing. | D4 §3.3.9 (impact / latency evidence) |
| `06_demonstrator_cell.png` | Photo of the real cell (Hänel + 2× JAKA + AGV + Basler camera). | D4 §3.3.8 (TRL6-7 demonstrator role) + `docs/05_role_in_demonstrator.md` |
| `07_hololens_ui.png` | HoloLens AR app — operator project selection screen. | D4 §3.3.8 + `docs/05_role_in_demonstrator.md` |
| `08_odoo_mo.png` | Odoo manufacturing-order view that drives the demonstrator. | `docs/01_arise_context.md` (ARISE alignment narrative) |

## Naming conventions

- Two digits + descriptive snake_case (`01_healthz.png`).
- PNG preferred over JPEG for crisp text; SVG when the source is a
  diagram tool.
- Keep file sizes < 1 MB where possible.

## Source / attribution

If a screenshot is derived from a third-party tool's UI (Grafana,
Orion-LD entity browser), include a brief credit in the alt text where
it's referenced. Photographs of the real cell should be cleared with
Ampero / Olorin before being committed publicly.

## Status

All eight TBD. Tracked in [`../../docs/D4_PLAN.md`](../../docs/D4_PLAN.md)
Sprint 1.
