# 03 — Installation & Hello World

> **Audience:** ARISE reviewer or third-party integrator running the
> adapter for the first time.
> **Reading time:** 5 minutes — installation + first response.
> **Pre-requisites:** Docker, Docker Compose, `curl`. **No ROS 2 / Hänel /
> Odoo installation on the host** is required for this page.

This page is the **clone-to-output** path. For a richer end-to-end
walkthrough with a mock Mission Controller and a real Odoo MO flowing
through, jump to [`04_basic_demo_how_to_use.md`](04_basic_demo_how_to_use.md)
after this.

## Dependency matrix

| Category | Required for Hello World | Required for the full demo (`04_*.md`) | Repository evidence |
|---|---|---|---|
| Operating system | Linux (Ubuntu 22.04 host tested) | Ubuntu 22.04 | this page |
| ROS 2 / Vulcanexus | inside the container; **not** on the host | inside the container | `Dockerfile`, `docker/docker-compose.demo.yml` |
| Python on host | not required | not required | `pyproject.toml` (only needed for local-dev, see §"Local dev" below) |
| Docker | ≥ 24 (Compose v2) | ≥ 24 | this page |
| FIWARE / Orion-LD | brought up by the demo compose | brought up by the demo compose | `docker/docker-compose.demo.yml` |
| Odoo | mock (`docker/odoo-mock/`) | mock or real | `docker/odoo-mock/` |
| Hardware | none | none for the in-repo demo; real Hänel + JAKA for the TRL6-7 demonstrator only | `docker/odoo-mock/`, `WAREHOUSE_BACKEND=null` |

The "Hello World" path uses **only mocks**. No real cobot, no real
warehouse, no real ERP.

## Hello World — five commands

The whole purpose of this section: a fresh reviewer clones the repo, runs
these commands, and sees a known-good response in under five minutes.

```bash
# 1) Clone the public repo.
git clone https://github.com/Ampero-SRL/hermes-odoo-adapter
cd hermes-odoo-adapter

# 2) Bring up the demo stack (adapter + Orion-LD + Mongo + Odoo mock + the
#    NullWarehouseClient). The first run pulls the Vulcanexus Humble base
#    image (~2 GB) — subsequent runs reuse the layer cache.
docker compose -f docker/docker-compose.demo.yml up -d

# 3) Wait for the adapter health endpoint to return ok (typically <30 s).
until curl -sf http://localhost:8080/healthz > /dev/null; do sleep 2; done
curl -s http://localhost:8080/healthz | jq .
```

Expected output for step 3:

```json
{
  "status": "ok",
  "version": "2.0.0",
  "subsystems": {
    "odoo": "ok",
    "orion": "ok",
    "warehouse": "ok (NullWarehouseClient)"
  }
}
```

```bash
# 4) Confirm the NGSI-LD entities the adapter exposes.
curl -s -H "Accept: application/ld+json" \
  http://localhost:1026/ngsi-ld/v1/entities?type=Project | jq '.[0].id'
# -> "urn:ngsi-ld:Project:<demo-project-id>" (from the seed scripts)
```

```bash
# 5) Call one ROS 2 service against the adapter from a Vulcanexus shell.
docker compose -f docker/docker-compose.demo.yml exec adapter \
    bash -lc '
        source /opt/ros/humble/setup.bash &&
        source /opt/hermes_ws/install/setup.bash &&
        ros2 service call /hermes/warehouse/pick \
            hermes_msgs/srv/WarehousePick \
            "{job_id: \"\", sku: \"ARTICOLO5\", quantity: 1}"
    '
```

Expected output for step 5:

```
requester: making request: hermes_msgs.srv.WarehousePick_Request(job_id='', sku='ARTICOLO5', quantity=1)
response:
hermes_msgs.srv.WarehousePick_Response(success=True, job_id='M<timestamp>-<hex>', error='')
```

The `success=True` + populated `job_id` mean the adapter accepted the
request and the `NullWarehouseClient` simulated the tray retrieval.

If you reached this point: **the adapter is running, NGSI-LD entities are
populated, and the ROS 2 service face is reachable from a sibling
container.** That's "Hello World" complete.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `curl: (7) Failed to connect to localhost port 8080` | Adapter container still booting. | `docker compose -f docker/docker-compose.demo.yml logs -f adapter` and wait for `Uvicorn running on 0.0.0.0:8080`. |
| `curl: (52) Empty reply from server` on `/healthz` | Vulcanexus image still pulling on first run. | Wait — base image is large; first `up` can take a few minutes. |
| `ros2 service call ... → service ... not available` | Adapter started but the ROS 2 node hasn't registered yet, or `ROS_DOMAIN_ID` mismatch. | Confirm `ROS_DOMAIN_ID=42` (adapter default). The exec shell must run inside the **same** container or the same DDS network. |
| `{"status":"error"}` on `/healthz` | One of the subsystems (Odoo mock / Orion-LD / Mongo) didn't come up. | `docker compose -f docker/docker-compose.demo.yml ps` — restart any container that exited. |
| `Orion entities empty` | The demo seeds may not have run yet. | Run the seed scripts: `docker compose ... exec adapter python -m scripts.seed_orion_demo`. |

If you hit something not in this table, check the adapter logs
(`docker compose ... logs adapter`) and please open an issue at
<https://github.com/Ampero-SRL/hermes-odoo-adapter/issues> with the log
extract + the output of `docker compose ... ps`.

## Local dev (optional, no Docker)

If you'd rather run the adapter directly on a host that already has
ROS 2 Humble + Vulcanexus + Python 3.10+:

```bash
# 1) Install Python deps.
poetry install --only main

# 2) Configure the environment (defaults point at the demo stack).
cp .env.example .env
# Edit .env to point at your Odoo / Orion-LD if not using the demo
# docker-compose stack.

# 3) Source ROS 2 + the vendored hermes_msgs, then run.
source /opt/ros/humble/setup.bash
# (Assumes you've built hermes_msgs in your workspace, see ros2_ws/.)
source ros2_ws/install/setup.bash
python -m hermes_odoo_adapter
```

This path is for adapter-internal development; the Hello World above is
the canonical entrypoint for reviewers and downstream users.

## What next?

- [`04_basic_demo_how_to_use.md`](04_basic_demo_how_to_use.md) — end-to-end Odoo MO → ROS 2 → mock-cobot flow with expected outputs at each step.
- [`02_interfaces.md`](02_interfaces.md) — full ROS 2 + NGSI-LD + HTTP + ROS4HRI interface reference.
- [`examples/`](../examples/) — runnable payload / curl / `ros2 service call` scripts that drive the adapter through the demo stack.
