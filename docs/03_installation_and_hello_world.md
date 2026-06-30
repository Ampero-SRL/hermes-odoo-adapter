# 03 — Installation & Hello World

> **Audience:** anyone running the adapter for the first time.
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
| Python on host | not required | not required | `pyproject.toml` (only needed for local-dev, see "Local dev" below) |
| Docker | ≥ 24 (Compose v2) | ≥ 24 | this page |
| FIWARE / Orion-LD | brought up by the demo compose | brought up by the demo compose | `docker/docker-compose.demo.yml` |
| Odoo | mock (`docker/odoo-mock/`) | mock or real | `docker/odoo-mock/` |
| Hardware | none | none for the in-repo demo; real Hänel + JAKA only for a hardware deployment | `docker/odoo-mock/`, `WAREHOUSE_BACKEND=null` |

The "Hello World" path uses **only mocks**. No real cobot, no real
warehouse, no real ERP.

## Hello World — five commands

> Hello World is intentionally minimal — it confirms the adapter
> process is up, the FastAPI face responds, and the ROS 2 / DDS face
> accepts a service call. Listing NGSI-LD entities and driving the
> end-to-end Odoo → Orion → ROS 2 → mock-cobot flow is the **basic
> demo** in [`04_basic_demo_how_to_use.md`](04_basic_demo_how_to_use.md).

The whole purpose of this section: clone the repo, run these commands,
and see a known-good response in under five minutes.

```bash
# 1) Clone the public repo.
git clone https://github.com/Ampero-SRL/hermes-odoo-adapter
cd hermes-odoo-adapter

# 2) Provide the runtime config. .env is gitignored and the demo compose
#    file expects it; the shipped .env.example contains sensible
#    NullWarehouseClient defaults.
cp .env.example .env

# 3) Bring up the demo stack (adapter + Orion-LD + Mongo + Odoo mock + the
#    NullWarehouseClient). The first run pulls the Vulcanexus Humble base
#    image (~2 GB) — subsequent runs reuse the layer cache.
docker compose -f docker/docker-compose.demo.yml up -d

# 4) Wait for the adapter health endpoint to return ok (typically <30 s).
until curl -sf http://localhost:8080/healthz > /dev/null; do sleep 2; done
curl -s http://localhost:8080/healthz | jq .
```

Expected output for step 4 (the liveness probe is intentionally cheap —
it does not check the backing subsystems):

```json
{
  "status": "healthy",
  "service": "hermes-odoo-adapter",
  "version": "2.0.0"
}
```

For per-subsystem readiness (Odoo / Orion / warehouse / ROS 2), hit
`/readyz` instead — it returns a `checks` map + a `details` map. See
[`../examples/curl/02_readyz.sh`](../examples/curl/02_readyz.sh).

```bash
# 5) Call one ROS 2 service against the adapter from a Vulcanexus shell.
docker compose -f docker/docker-compose.demo.yml exec adapter \
    bash -lc '
        source /opt/ros/humble/setup.bash &&
        source /opt/hermes_ws/install/setup.bash &&
        ros2 service call /hermes/warehouse/pick \
            hermes_msgs/srv/WarehousePick \
            "{job_id: \"\", sku: \"SCH-REL-24V\", quantity: 1}"
    '
```

Expected output for step 5 (empty `job_id` request → adapter assigns one
as `J-<8 hex chars>`):

```
requester: making request: hermes_msgs.srv.WarehousePick_Request(job_id='', sku='SCH-REL-24V', quantity=1)
response:
hermes_msgs.srv.WarehousePick_Response(success=True, job_id='J-1a2b3c4d', error='')
```

The `success=True` + populated `job_id` mean the adapter accepted the
request and the `NullWarehouseClient` simulated the tray retrieval. The
hex part of the `job_id` will differ on every call.

If you reached this point: **the adapter is running, the FastAPI face
responded, and the ROS 2 service face is reachable from a sibling
container.** That's "Hello World" complete. Creating NGSI-LD entities
(`Project` → `Reservation` / `Shortage`) and driving the end-to-end
Odoo → Orion → ROS 2 pipeline is the basic demo in
[`04_basic_demo_how_to_use.md`](04_basic_demo_how_to_use.md).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `curl: (7) Failed to connect to localhost port 8080` | Adapter container still booting. | `docker compose -f docker/docker-compose.demo.yml logs -f adapter` and wait for `Uvicorn running on 0.0.0.0:8080`. |
| `curl: (52) Empty reply from server` on `/healthz` | Vulcanexus image still pulling on first run. | Wait — base image is large; first `up` can take a few minutes. |
| `Bind for 0.0.0.0:8080 failed: port is already allocated` (or `:1026` / `:27017` / `:8069`) | Another container or host process is squatting the port. | `docker ps --format 'table {{.Names}}\t{{.Ports}}'` to find it. The deployment-side compose under `hermes_main/deployment/` uses the same ports; stop those containers (`docker stop deployment-*-1`) before running the demo stack, or remap the demo ports via a `docker-compose.override.yml`. |
| `ros2 service call ... → service ... not available` | Adapter started but the ROS 2 node hasn't registered yet, or `ROS_DOMAIN_ID` mismatch. | Confirm `ROS_DOMAIN_ID=42` (adapter default). The exec shell must run inside the **same** container or the same DDS network. |
| `{"status":"error"}` on `/healthz` (or `not_ready` on `/readyz`) | One of the subsystems (Odoo mock / Orion-LD / Mongo) didn't come up. | `docker compose -f docker/docker-compose.demo.yml ps` — restart any container that exited. Check `/readyz` for the per-subsystem `details` map. |
| `error parsing value for field "inventory_allowed_skus"` at adapter startup | Stale `.env` from before commit `dbde58d`. | `cp .env.example .env` again (the commit added a `NoDecode` annotation so comma-separated lists work; older `.env` files predate the fix). |
| `[odoo-mock 6/7] COPY data/ ./data/: "/data": not found` at build time | Stale clone from before commit `2a2ce0d`. | `git pull` and rebuild — the seed data under `docker/odoo-mock/data/` was gitignored in the first cut of the repo. |
| `LdContextNotAvailable: http://localhost:8080/context.jsonld` from Orion when creating a `Project` | The `@context` URL points at the host loopback, which Orion can't reach from inside the compose network. | Use `http://adapter:8080/context.jsonld` (compose hostname). The shipped `examples/payloads/*.json` already use the right URL. |
| Second `POST /admin/recompute/<id>` doesn't fire any worker activity | The idempotency cache holds the most recent `(project_id, data)` hash for the project. | `curl -X DELETE http://localhost:8080/admin/idempotency/<project_id>` before the second recompute. The cache exists on purpose to avoid duplicate work when Orion notifies twice for the same `Project`. |

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
the canonical entrypoint for downstream users.

## What next?

- [`04_basic_demo_how_to_use.md`](04_basic_demo_how_to_use.md) — end-to-end Odoo MO → ROS 2 → mock-cobot flow with expected outputs at each step.
- [`02_interfaces.md`](02_interfaces.md) — full ROS 2 + NGSI-LD + HTTP + ROS4HRI interface reference.
- [`examples/`](../examples/) — runnable payload / curl / `ros2 service call` scripts that drive the adapter through the demo stack.
