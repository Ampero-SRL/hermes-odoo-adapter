# Captured demo evidence

Text logs captured 2026-06-10 by running the full Sprint 1.5
fresh-clone reproducibility test:

```
git clone https://github.com/Ampero-SRL/hermes-odoo-adapter
cd hermes-odoo-adapter
cp .env.example .env
docker compose -f docker/docker-compose.demo.yml up -d
```

…then exercising the documented demo flow (Stage 1–3 of
[`../../docs/04_basic_demo_how_to_use.md`](../../docs/04_basic_demo_how_to_use.md))
and capturing the responses / log lines into the files below. These
plain-text artefacts are easier to inspect / diff / cite than PNG
screenshots and don't depend on any rendering pipeline.

## Files

| File | What it proves |
|---|---|
| [`01_healthz.log`](01_healthz.log) | The adapter's liveness endpoint returns the expected `{status: healthy, service: hermes-odoo-adapter, version: 2.0.0}` shape from a fresh clone. |
| [`02_readyz.log`](02_readyz.log) | All four subsystems (Odoo, Orion-LD, warehouse `null` backend, ROS 2 node `hermes_adapter`) are reachable. |
| [`03_stack_status.log`](03_stack_status.log) | `docker compose ps` output showing the four containers (adapter, mongo, odoo-mock, orion-ld) all `Up`. |
| [`04_adapter_startup.log`](04_adapter_startup.log) | First ~40 lines of the adapter's startup log — proves the Odoo / Orion / WarehouseClient initialisations, the ROS 2 node coming up, **`ROS4HRI Intent publisher up on /intents (hri_actions_msgs.msg.Intent)`** (Sprint 0.4 live!) and **`ROS4HRI Intent publisher wired into ProjectSyncWorker`**. |
| [`05_intent_published.log`](05_intent_published.log) | Adapter log lines from the actual end-to-end demo run. Two `Published ROS4HRI Intent: START_ACTIVITY mo=1 project=demo-ctrl-1 source=erp/odoo bom_lines=4` lines (one per recompute), each immediately followed by the corresponding `Shortage` or `Reservation` create + Project status patch. **This is the Sprint 0.4 hero artefact.** |
| [`06_project_entity.log`](06_project_entity.log) | The `urn:ngsi-ld:Project:demo-ctrl-1` entity after the Shortage flow: status moved from `requested` → `shortage`. |
| [`07_shortage_entity.log`](07_shortage_entity.log) | The `urn:ngsi-ld:Shortage:demo-ctrl-1` entity (default mock data path): `WAGO-221-412` is short 4 of the 6 required (only 2 in stock). |
| [`08_metrics.log`](08_metrics.log) | Adapter `/metrics` Prometheus output — every NGSI-LD operation timing, Odoo call timing, warehouse call counters. Useful for D4 §3.3.9 latency / performance evidence. |
| [`09_reservation_entity.log`](09_reservation_entity.log) | The `urn:ngsi-ld:Reservation:demo-ctrl-1` entity after the top-up flow: 4 BOM lines (`SCH-REL-24V` ×4, `ABB-MCB-10A` ×2, `DIN-TERM-2.5` ×8, `WAGO-221-412` ×6) under one Reservation, status `pending`, source `odoo`. |
| [`10_ros2_topics.log`](10_ros2_topics.log) | `ros2 topic list` (best-effort — the ros2 CLI's RPC daemon was flaky inside the test container; the actual topic list is shown definitively in `04_adapter_startup.log`'s "topics:" line). |

## What's still TBD (image / video evidence)

The text logs above cover the CLI / API surface end-to-end. The
following items still need actual UI / hardware capture and are tracked
in [`../../docs/D4_PLAN.md`](../../docs/D4_PLAN.md) Sprint 1:

| Asset | Source |
|---|---|
| Demonstrator video (3–5 min, end-to-end real cell run) | See [`../video_link.md`](../video_link.md) — needs a live recording of the production cell. |
| Grafana dashboard screenshot | Grafana is bundled in `docker/docker-compose.full.yml` (port 3000); capture the per-NGSI-LD latency panel after a representative run. |
| Demonstrator cell photo | Hardware shot (Hänel + 2× JAKA + AGV + Basler camera) — taken on site. |
| HoloLens AR UI screenshot | Per-project selection / placement guidance screens — taken from the running HoloLens app. |
| Odoo MO view screenshot | The manufacturing order that drives the demo — taken in the production Odoo. |

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
