# Third-party licenses

Runtime Python dependencies the HERMES Odoo Adapter ships against (per
`pyproject.toml` → `[tool.poetry.dependencies]`, resolved versions from
`poetry.lock`, validated by introspecting the installed packages inside
the production Docker image).

All licenses are OSI-approved permissive licenses compatible with this
project's own **Apache-2.0** distribution (see [`LICENSE`](LICENSE) +
[`NOTICE`](NOTICE) for the headline attribution).

| Package | Version | License | One-line description |
|---|---|---|---|
| `asyncio-throttle` | `1.0.2` | MIT | Simple async throttler. |
| `fastapi` | `0.104.1` | MIT | The FastAPI web framework. |
| `httpx` | `0.25.2` | BSD-3-Clause | Async HTTP client used by `OdooClient` and `OrionClient`. |
| `jsonschema` | `4.25.1` | MIT | Runtime validation of the four NGSI-LD entity schemas under `contracts/schemas/`. |
| `lxml` | `5.4.0` | BSD-3-Clause | XML processing — pulled in by `zeep` for the Hänel SOAP path. |
| `prometheus-client` | `0.19.0` | Apache-2.0 | Exposes `/metrics`. |
| `pydantic` | `2.12.4` | MIT | Settings + request/response model validation. |
| `pydantic-settings` | `2.12.0` | MIT | Env-driven `Settings` class in `settings.py`. |
| `python-dotenv` | `1.2.1` | BSD-3-Clause | Loads `.env` files in dev. |
| `structlog` | `23.3.0` | Apache-2.0 | Structured (JSON) logs. |
| `tenacity` | `8.5.0` | Apache-2.0 | Retry decorators on the NGSI-LD / JSON-RPC / SOAP clients. |
| `uvicorn` | `0.24.0.post1` | BSD-3-Clause | ASGI server for FastAPI. |
| `zeep` | `4.3.2` | MIT | SOAP 1.1 client used by `HanelSoapClient`. |

## ROS 2 / Vulcanexus dependencies

The Docker image is built on **`eprosima/vulcanexus:humble`** (Apache-2.0)
and additionally colcon-builds two ROS 2 message packages from source
into the runtime workspace:

| Package | Source | License | Used for |
|---|---|---|---|
| `hermes_msgs` | vendored at [`ros2_ws/src/hermes_msgs/`](ros2_ws/src/hermes_msgs/) (snapshot of `hermes_main`@`9987978`) | Apache-2.0 | The 5 service / 1 message types the adapter publishes (`WarehousePick`, `ConsumeStock`, `ProduceStock`, `WarehousePickStatus`, `WarehousePickCancel`, `InventoryUpdate`). |
| `hri_actions_msgs` | upstream [`ros4hri/hri_actions_msgs@humble-devel`](https://github.com/ros4hri/hri_actions_msgs) — fetched via [`ros2_ws/deps.repos`](ros2_ws/deps.repos) at build time | Apache-2.0 | The ROS4HRI `Intent` message the adapter publishes on `/intents` (Sprint 0.4). |

The `hermes_odoo_adapter_launch` ament_python wrapper at
[`ros2_ws/src/hermes_odoo_adapter_launch/`](ros2_ws/src/hermes_odoo_adapter_launch/)
is Apache-2.0 (this project).

## Refresh procedure

Re-run the introspection against the latest production image:

```bash
docker compose -f docker/docker-compose.demo.yml build adapter
docker run --rm --entrypoint /bin/bash docker-adapter -c '
    source /opt/ros/humble/setup.bash
    python3 -c "
import importlib.metadata as md
WANT = [<paste pyproject dep names>]
for name in WANT:
    dist = md.distribution(name)
    print(name, dist.version, dist.metadata.get(\"License\"))
"
'
```

…and update the table above. The list of WANT packages should track
`[tool.poetry.dependencies]` in `pyproject.toml` (excluding `python`).

## License compatibility

| This project | Apache-2.0 |
|---|---|
| Permissive runtime deps (Apache-2.0 / MIT / BSD-3-Clause / BSD) | ✅ compatible — distribute under Apache-2.0 with attribution preserved (see [`NOTICE`](NOTICE)). |
| LGPL / GPL / AGPL components | None at runtime. |
| Commercial closed-source components | None. The production Hänel HOST-COM controller is *interacted with*, but its firmware is not redistributed by this repo. |
