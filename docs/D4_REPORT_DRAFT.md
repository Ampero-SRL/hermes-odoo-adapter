# D4 — Shareable HRI Module: HERMES Odoo Adapter (working draft)

> **Status:** working draft, fills the ARISE D4 §3.1 – §3.4 template inline.
> Placeholders `[TBD: …]` mark items that still need a decision, an external
> link or a verified value. See [`D4_PLAN.md`](D4_PLAN.md) for the
> companion task plan.

---

## 3.1 Project identification sheet

| Field | Information |
|---|---|
| Project title | HERMES — Hybrid ERP + Robotics Manufacturing Cell |
| Project acronym | HERMES |
| Lead organisation | Ampero S.r.l. |
| Contact person | Francesco Solinas — `francesco.solinas@olorin.tech` — Ampero S.r.l. |
| Technical contact for the repository | Francesco Solinas — `francesco.solinas@olorin.tech` — Ampero S.r.l. — GitHub: `@<TBD>` |
| Assigned ARISE mentor | [TBD: name / email / organisation] |
| Reusable module name | **HERMES Odoo Adapter** |
| GitHub repository URL | <https://github.com/Ampero-SRL/hermes-odoo-adapter> |
| Release/tag submitted for review | `v0.4.0-d4` *(cut after Sprint 1.5 fresh-clone reproducibility check passes — see D4_PLAN.md)* |
| Demonstrator video URL | [TBD: confirm or record end-to-end Odoo → Orion → ROS 2 → robot sequence; placeholder until link captured] |

---

## 3.2 GitHub repository

### 3.2.1 Repository identification and access

| Item | Value |
|---|---|
| Repository name | `hermes-odoo-adapter` |
| Repository owner/organisation | `Ampero-SRL` (GitHub) |
| Repository URL | <https://github.com/Ampero-SRL/hermes-odoo-adapter> |
| Visibility during review | Public |
| Submitted release / tag | `v0.4.0-d4` *(pending — see plan)* |
| Main branch | `main` |
| Primary programming language(s) | Python (3.10+) |
| Primary runtime environment | Vulcanexus Humble (Fast-DDS) + Docker; FastAPI + `rclpy` in a single process |
| Issue tracker enabled | Yes — GitHub Issues |

**Access:**

| Access requirement | Status |
|---|---|
| ARISE reviewer access | Repository is public; reviewers can clone without credentials. Videos and documentation linked from the README. |
| Public availability | Public **now**. |
| External dependencies needed for the minimum example | `hermes_msgs` (ROS 2 message package) is **vendored** under `ros2_ws/src/hermes_msgs/` (see `ros2_ws/src/hermes_msgs/VENDORED_FROM.md`). `hri_actions_msgs` (ROS4HRI, for the Intent publisher) is fetched via `ros2_ws/deps.repos` if the `ros-humble-hri-actions-msgs` apt package is unavailable. All other dependencies (Vulcanexus Humble base image, Orion-LD, Odoo, mock services) are pulled by `docker compose -f docker/docker-compose.demo.yml up`. **No private repositories, binaries or hardware drivers are required for the hello world.** |
| Repository stability | The submitted tag `v0.4.0-d4` will not be modified during the review period and will remain stable until **2033-06-30** (six years after ARISE ends on 2027-06-30). |

### 3.2.2 License, ownership and maintainership

| Aspect | Value |
|---|---|
| Open implementation license | **Apache-2.0** — see [`LICENSE`](../LICENSE) |
| Copyright owner(s) | Ampero S.r.l. |
| Third-party licenses | See [`NOTICE`](../NOTICE); managed Python dependencies under various OSI-approved licenses (Apache-2.0, MIT, BSD), listed in `pyproject.toml`. |
| Maintainer | Francesco Solinas — `francesco.solinas@olorin.tech` — Ampero S.r.l. — GitHub: `@<TBD>` |
| Maintenance commitment | Best effort beyond D4; commercial support paths under Ampero S.r.l. on request. |
| Commercial/proprietary boundary | Open: the entire adapter (Python source, contracts, Dockerfiles, mock backends). Excluded from the open distribution: the live Hänel HOST-COM controller credentials, the production Odoo instance, and the customer-specific BOM data. The `NullWarehouseClient` (in-tree dev stub) is sufficient to exercise the full pipeline end-to-end without the proprietary parts. |

### 3.2.3 Scope of the open implementation

| Component / capability | Status | Repository path / evidence | Notes |
|---|---|---|---|
| Vulcanexus / ROS 2 node (`HermesAdapterNode`) — DDS face of the adapter | **Open** | `src/hermes_odoo_adapter/ros2_node.py` | 5 service servers + 3 publishers + 1 subscriber; runs in a background thread alongside FastAPI. |
| FastAPI HTTP face — health, metrics, NGSI-LD notifications, admin | **Open** | `src/hermes_odoo_adapter/main.py` | Endpoints listed in the README and `config/README.md`. |
| Odoo JSON-RPC client | **Open** | `src/hermes_odoo_adapter/odoo_client.py` | BOM resolution, stock moves, MO polling. |
| Orion-LD NGSI-LD client | **Open** | `src/hermes_odoo_adapter/orion_client.py` | CRUD + PATCH against Orion; project / reservation / shortage / inventory-item entities. |
| Hänel SOAP 1.1 client (`HanelSoapClient`) | **Open interface, mock backend** | `src/hermes_odoo_adapter/warehouse/*` | The class is open; the production Hänel endpoint and credentials are *not* part of the open distribution. `NullWarehouseClient` replicates the behaviour for hello world / demo. |
| NGSI-LD context + JSON Schemas | **Open** | `contracts/context/context.jsonld`, `contracts/schemas/{Project,Reservation,InventoryItem,Shortage}.schema.json` | Canonical FIWARE artefacts for the entities the adapter manages. |
| `hermes_msgs` ROS 2 messages | **Vendored open** | `ros2_ws/src/hermes_msgs/` | See `VENDORED_FROM.md`. |
| Docker / Compose runtime | **Open** | `Dockerfile`, `docker/docker-compose.{full,demo}.yml`, `docker/odoo-mock/` | Hello-world path uses the demo compose with all mocks. |
| ROS4HRI `Intent` publisher | **Planned (Sprint 0.4)** | `src/hermes_odoo_adapter/ros2_node.py` (Odoo MO Intent), plus companion in `hermes_main/hololens_api/` for AR-operator intents | See §3.3.5 + `D4_PLAN.md` §4.4. |
| DDS Enabler configuration | **N/A** | `config/README.md` | Documented N/A with topic↔entity mapping; the adapter performs the bridging in-process. |

### 3.2.4 Repository structure (current)

```
hermes-odoo-adapter/
  README.md
  LICENSE
  NOTICE
  pyproject.toml
  Dockerfile
  Makefile
  contracts/
    context/context.jsonld
    schemas/{Project,Reservation,InventoryItem,Shortage}.schema.json
  config/
    README.md                # DDS enabler N/A + topic <-> entity mapping
  docker/
    docker-compose.full.yml  # production-ish stack (Odoo, Orion, Mongo, adapter)
    docker-compose.demo.yml  # demo / hello-world stack (mocks + adapter)
    odoo-mock/, odoo-config/, prometheus-config/, grafana-config/
  docs/
    D4_PLAN.md               # internal task plan
    D4_REPORT_DRAFT.md       # this document
    01_arise_context.md
    02_interfaces.md
    03_installation_and_hello_world.md
    04_basic_demo_how_to_use.md
    05_role_in_demonstrator.md
  ros2_ws/
    deps.repos               # ROS 2 dependency manifest (hri_actions_msgs)
    src/hermes_msgs/         # vendored from hermes_main (see VENDORED_FROM.md)
  scripts/
    docker-entrypoint*.sh
    seed_*.py
    normalize_env.py
  src/hermes_odoo_adapter/
    main.py, ros2_node.py, odoo_client.py, orion_client.py, settings.py,
    warehouse/, utils/
  tests/
    unit/, integration/
  examples/
    payloads/, curl/, ros2/  # runnable demo flows (see examples/README.md)
  launch/
    hermes_odoo_adapter.launch.py  # `ros2 launch` ExecuteProcess wrapper
  media/
    architecture_diagram.md  # Mermaid system-context diagram
    sequence_diagram.md      # Mermaid sequence diagrams (Shortage / Reservation / pick)
    video_link.md            # demonstrator video URL (TBD)
    screenshots/             # PNG inventory + shot list (TBD captures)
  project_mapping.json        # Project code -> Odoo product mapping (shipped in the image)
```

### 3.2.5 README content — already present

The current [`README.md`](../README.md) covers: module introduction, architecture
diagram (ASCII), key components, quick start, configuration, ROS 2 interfaces
(services + topics tables), HTTP API endpoints, warehouse backends, NGSI-LD
entities. Pending sections for D4 §3.2.5 compliance (tracked in `D4_PLAN.md`
Sprint 2):

- [TBD] Connection-with-ARISE narrative (Vulcanexus / FIWARE / DDS / ROS4HRI).
- [TBD] Target-platforms summary table (tested / expected / not supported).
- [TBD] Robot missions and tasks mapping.
- [TBD] Off-the-shelf capabilities table.
- [TBD] "Hello World" vs "Basic demo" split with expected outputs.
- [TBD] Known limitations + proprietary boundary.
- [TBD] Citation / contact block.

### 3.2.6 Interface documentation

**ROS 2 / Vulcanexus** — current interfaces:

| Element | Name | Type | Description |
|---|---|---|---|
| Node | `hermes_adapter` (default; override via `ROS2_NODE_NAME`) | `rclpy.Node` | Hybrid DDS + FastAPI; background `rclpy.spin` thread. |
| Service | `/hermes/warehouse/pick` | `hermes_msgs/srv/WarehousePick` | Initiate tray retrieval; routes through `HanelHostComClient` / `HanelSoapClient` / `NullWarehouseClient`. |
| Service | `/hermes/warehouse/status` | `hermes_msgs/srv/WarehousePickStatus` | Poll retrieval progress. |
| Service | `/hermes/warehouse/cancel` | `hermes_msgs/srv/WarehousePickCancel` | Cancel an in-flight retrieval. |
| Service | `/hermes/stock/consume` | `hermes_msgs/srv/ConsumeStock` | Decrement Odoo stock + NGSI-LD `InventoryItem` after cobot pick. |
| Service | `/hermes/stock/produce` | `hermes_msgs/srv/ProduceStock` | Increment finished-product stock. |
| Publisher | `/hermes/inventory_updates` | `hermes_msgs/msg/InventoryUpdate` | Stock change events. |
| Publisher (latched) | `/hermes/warehouse/tray_state` | `std_msgs/Int16` | Current-tray state from Hänel HOST-COM. |
| Publisher | `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | Health of warehouse / Odoo / Orion subsystems. |
| Subscriber | `/hermes/mission_state` | `std_msgs/String` (JSON payload) | Mission-state stream → patches FIWARE entities. |
| Publisher | `/intents` | `hri_actions_msgs/Intent` | ROS4HRI alignment — Odoo MO planner-derived intent (`intent=START_ACTIVITY`, `source=erp/odoo`, `modality=MODALITY_OTHER`). See §3.3.5. |
| Launch file | [`launch/hermes_odoo_adapter.launch.py`](../launch/hermes_odoo_adapter.launch.py) | `launch` | `ros2 launch ./launch/hermes_odoo_adapter.launch.py` (path-based — adapter is Poetry-only, not an ament package). `ExecuteProcess` wrapper around `python -m hermes_odoo_adapter`. Launch arguments: `ros2_node_name` / `warehouse_backend` / `log_level`. |

**FIWARE / NGSI-LD interface:**

- `@context`: [`contracts/context/context.jsonld`](../contracts/context/context.jsonld)
- Entity types managed: `Project`, `Reservation`, `Shortage`, `InventoryItem` (schemas in [`contracts/schemas/`](../contracts/schemas/))
- Endpoint: Orion-LD HTTP REST (configurable via env `ORION_URL`; default `http://orion-ld:1026`).
- Payload examples: [`examples/payloads/{project,reservation,inventory_item,shortage}.json`](../examples/payloads/) — minimal NGSI-LD payloads matching the contracts schemas.
- Notification subscriptions: adapter exposes `POST /orion/notifications` to receive Orion-LD subscriptions on `Project` requests.

**DDS NGSI-LD enabler:**

| Item | Value |
|---|---|
| DDS Enabler used | No |
| Justification | In-process bridging — see [`config/README.md`](../config/README.md). |
| Topic ↔ entity mapping | [`config/README.md`](../config/README.md) — canonical table. |
| Test command / script | [`examples/curl/`](../examples/curl/) + [`examples/ros2/`](../examples/ros2/) — runnable HTTP + ROS 2 scripts that exercise the documented mapping end-to-end against the demo compose. |
| Known limitations | Custom QoS profile not yet shipped; defaults inherited from Vulcanexus base. |

**ROS4HRI / ROS4RI:** see §3.3.5 below — **Used** (Intent publisher).

### 3.2.7 Installation, hello world and basic demo

Pending Sprint 1.5 fresh-clone reproducibility validation. Target acceptance:

```
git clone https://github.com/Ampero-SRL/hermes-odoo-adapter
cd hermes-odoo-adapter
cp .env.example .env
docker compose -f docker/docker-compose.demo.yml up -d
curl -s http://localhost:8080/healthz       # -> {"status":"healthy","service":"hermes-odoo-adapter","version":"2.0.0"}
ros2 service call /hermes/warehouse/pick \
    hermes_msgs/srv/WarehousePick "{job_id:'', sku:'SCH-REL-24V', quantity:1}"
# -> expected response logged in docs/03_installation_and_hello_world.md
```

| Dependency category | Required for hello world | Required for full demo | Repository evidence |
|---|---|---|---|
| Operating system | Linux (Ubuntu 22.04 host) | Ubuntu 22.04 | README §Prerequisites |
| ROS 2 / Vulcanexus | Vulcanexus Humble in container (no host install) | Vulcanexus Humble | Dockerfile, `docker/docker-compose.demo.yml` |
| Python | 3.10+ (only for local dev) | 3.10+ | `pyproject.toml`, `poetry.lock` |
| Docker | Yes | Yes | `docker/docker-compose.{demo,full}.yml` |
| FIWARE Context Broker | Orion-LD (in compose) | Orion-LD | `docker/docker-compose.demo.yml` |
| Hardware | None | Hänel MP 12N + JAKA Pro 16 + ASRS cell | [TBD docs link] |
| Simulation / recorded data | `NullWarehouseClient` + `odoo-mock` | Real Hänel + Odoo | `docker/odoo-mock/` + `WAREHOUSE_BACKEND=null` |

### 3.2.8 Repository evidence checklist

- [x] README provides a clear module introduction and ARISE connection. *(connection narrative TBD in Sprint 2)*
- [x] LICENSE file is included.
- [x] The open implementation, wrapper, adapter, mock and simulation path is present.
- [x] Repository structure is documented (this section).
- [x] ROS 2/Vulcanexus interfaces are documented.
- [x] FIWARE/NGSI-LD interface or mapping is documented.
- [x] DDS enabler configuration: explicit N/A documented with the alternative path.
- [ ] ROS4HRI/ROS4RI usage documented. *(Sprint 0.4 — Intent publisher + §3.3.5 table)*
- [x] Installation instructions list software, hardware and simulation dependencies separately.
- [ ] Hello world can be executed using the submitted release/tag. *(Sprint 1.5)*
- [x] Basic demo has commands, expected outputs and visual evidence. *([`docs/04_basic_demo_how_to_use.md`](04_basic_demo_how_to_use.md) + the Mermaid diagrams in [`media/`](../media/); per-stage screenshots still TBD.)*
- [x] Role in the TRL6-7 demonstrator is documented. *([`docs/05_role_in_demonstrator.md`](05_role_in_demonstrator.md))*
- [ ] Video link and screenshots are available. *(Video URL TBD — see [`media/video_link.md`](../media/video_link.md); screenshot shot list at [`media/screenshots/README.md`](../media/screenshots/README.md).)*
- [x] Known limitations and proprietary boundaries are explicit *(in §3.2.2 and §3.3.10)*.
- [x] Maintainer/contact information is included *(in §3.2.1 / §3.2.2)*.

---

## 3.3 Written report

### 3.3.1 Executive module summary

| Question | Answer |
|---|---|
| What is the reusable module? | A hybrid **Vulcanexus / ROS 2 + FastAPI** Python process that bridges three industrial sub-systems used in a mixed-robotics assembly cell: an **ERP** (Odoo, JSON-RPC), a **FIWARE context broker** (Orion-LD, NGSI-LD), and a **warehouse controller** (Hänel vertical lift, SOAP 1.1). It exposes the warehouse + stock operations as ROS 2 services consumable by a Mission Controller, maintains the FIWARE digital-twin entities (`Project`, `Reservation`, `Shortage`, `InventoryItem`), and propagates Mission Controller state back into FIWARE. |
| What problem does it solve? | The bottleneck between a generic robotics cell and a real factory's planning + warehouse systems. Mission Controllers want clean ROS 2 service calls; ERPs want JSON-RPC + customer BOMs; vertical lifts want SOAP / HOST-COM telegrams; the operator-facing FIWARE digital twin wants NGSI-LD entities. The adapter is the single process that speaks all four. |
| What does it provide off-the-shelf? | Five warehouse / stock ROS 2 services; bidirectional NGSI-LD entity management; a pluggable warehouse backend (`HanelSoapClient` for production; `NullWarehouseClient` for dev/test); Mission-state subscription that patches FIWARE entities; Prometheus metrics; structured logs. |
| Who is the intended user? | Robotics system integrators building ERP-driven mixed-robotics cells; ARISE TEF operators; ERP teams who want to expose Odoo manufacturing orders to a robotics stack without writing a custom bridge. |
| What is the minimum reproducible execution path? | `docker compose -f docker/docker-compose.demo.yml up` — all-mocks stack; runs without real hardware. |
| Main evidence of validation | [TBD: HERMES TRL6-7 demonstrator video URL + metrics from the production deployment.] |

### 3.3.2 Relation with ARISE and previous milestones

| Milestone | Relevant result | Reflected in the shareable module |
|---|---|---|
| Stage 1 — Individual Mentoring Plan | [TBD: scope + need / challenge per Stage 1 deliverable] | Defined the "ERP-driven robotics cell" scope that motivated a dedicated adapter. |
| Stage 2 — Proof of Concept | [TBD: PoC URL + key result] | Proved the Odoo ↔ Orion-LD ↔ ROS 2 round-trip; the v2.0 adapter is the productionised version of that PoC. |
| Stage 3 — TRL6-7 Demonstrator | HERMES end-to-end pipeline: Odoo MO → adapter → Orion-LD → Mission Controller → JAKA Pro 16 + Hänel ASRS + AGV. | The adapter is the integration backbone; this module extracts it as a reusable component. |
| Stage 4 — Shareable module | This D4 package. | See [`docs/D4_PLAN.md`](D4_PLAN.md) and the GitHub repo. |

[TBD: ARISE alignment narrative — 1–2 paragraphs on Vulcanexus / FIWARE / DDS / ROS4HRI.]

### 3.3.3 Platforms, missions and tasks addressed

| Platform / setting | Tested | Expected compatibility | Limitations |
|---|---|---|---|
| Manipulator / cobot | Yes — JAKA Pro 16 (×2, JAKA SDK V2.3.1, gRPC + TCP) | Any ROS 2-driven cobot whose driver exposes joint trajectories and a vacuum/gripper service | Adapter does not directly drive the cobot; it interacts via the Mission Controller's services. |
| Mobile robot / AMR / AGV | Yes — XBOT AGV (433 MHz / RS485 wireless) | Any AGV exposing a docking action via ROS 2 (e.g. `nav2`) | Routing logic lives in the Mission Controller, not in the adapter. |
| Industrial cell / PLC | Yes — Hänel MP 12N controller (TCP HOST-COM telegrams via `HanelHostComClient`; HOST-WEB SOAP 1.1 fallback via `HanelSoapClient`) | Any vertical lift / vertical carousel that can sit behind the `WarehouseClient` interface | Built-in backends: `HanelHostComClient`, `HanelSoapClient`, `NullWarehouseClient`. Another vendor needs ≈300 LOC of `WarehouseClient` subclass. |
| Sensors | Yes — Basler a2A3840-45ucPRO 4K USB3 (Jetson DINOv2 + grabcut detection) | Any RGB camera + detection node that publishes `hermes_msgs/msg/DetectedComponent` and downstream `hermes_msgs/msg/InventoryUpdate` consumers | Detection is upstream of this module; the adapter is *not* a subscriber of `/hermes/inventory_updates` — it is the **publisher** (downstream consumers like dashboards or the Mission Controller subscribe). |
| Simulator / recorded data | Yes — `NullWarehouseClient` + `docker/odoo-mock` | Any environment running Docker + Orion-LD | No Gazebo / Isaac Sim integration is needed for the adapter's hello world. |

**Missions contributed to:**

| Mission type | Contributes? | Explanation |
|---|---|---|
| Collaborative assembly | Yes | Provides the BOM-driven pick orders and stock reconciliation that drive an assembly cell. |
| Human-aware navigation | No | Out of scope — the adapter is not a perception module. |
| Object handover | Yes — indirectly | Triggers the Mission Controller's handover via the `WarehousePick` + `ConsumeStock` services. |
| Operator monitoring or assistance | Yes — via NGSI-LD | Surfaces `Project.status`, `Reservation.status`, `Shortage` to any FIWARE-aware operator dashboard. |
| Quality inspection | No | Out of scope. |
| Intralogistics | Yes | Vertical-lift integration + stock moves + AGV-feed orchestration via Mission Controller. |
| Teleoperation or remote supervision | Partial | Operator selection from the HoloLens AR app (Mission Controller side) is propagated back to FIWARE by the adapter. |
| Safety-aware task execution | No | Out of scope. |
| Other | — | — |

**Tasks supported by the module:**

| Task | Input | Output | Status |
|---|---|---|---|
| Resolve Bill of Materials for a manufacturing order | `Project` entity (NGSI-LD), Odoo MO id | `Reservation` (NGSI-LD) with BOM lines + `Shortage` if applicable | Implemented |
| Initiate a warehouse pick | `hermes_msgs/srv/WarehousePick` request | Tray presented at the Hänel pickup point + status updates | Implemented |
| Decrement / increment stock after pick / produce | `hermes_msgs/srv/{ConsumeStock,ProduceStock}` | Odoo stock move + NGSI-LD `InventoryItem.quantity` update + `/hermes/inventory_updates` event | Implemented |
| Bridge Mission Controller state into FIWARE | `std_msgs/String` JSON on `/hermes/mission_state` | NGSI-LD entity patches | Implemented |
| Continuous Odoo ↔ FIWARE inventory sync | Odoo stock state | NGSI-LD `InventoryItem` updates | Implemented |
| Publish planner intents (ROS4HRI) — operator-side intents are published from companion nodes in `hermes_main` | Odoo MO ingestion (planner intent) | `hri_actions_msgs/Intent` on `/intents` (`START_ACTIVITY`, `source=erp/odoo`) | **Implemented (Sprint 0.4)** |

### 3.3.4 Off-the-shelf capabilities

| Capability | Input | Output | Interface | Status |
|---|---|---|---|---|
| Warehouse pick orchestration | ROS 2 service call | DDS reply + Hänel HOST-COM telegrams | ROS 2 / SOAP | Implemented + tested |
| Stock consume / produce | ROS 2 service call | Odoo stock move + NGSI-LD patch | ROS 2 / JSON-RPC / NGSI-LD | Implemented + tested |
| BOM resolution + shortage detection | NGSI-LD `Project` request | `Reservation` + `Shortage` entities | NGSI-LD | Implemented |
| Inventory streaming | (background worker) | `/hermes/inventory_updates` topic + NGSI-LD `InventoryItem` updates | DDS / NGSI-LD | Implemented |
| Mission-state to FIWARE bridge | DDS subscription | NGSI-LD entity patches | DDS / NGSI-LD | Implemented |
| Planner ROS4HRI Intent publishing (operator intents come from companion nodes in `hermes_main`) | Odoo MO ingestion | `hri_actions_msgs/Intent` on `/intents` (`START_ACTIVITY`, `source=erp/odoo`) | DDS (ROS4HRI) | Implemented (Sprint 0.4) |

### 3.3.5 Interoperability evidence

| Interoperability area | Evidence | Link |
|---|---|---|
| ROS 2 / Vulcanexus | 5 service servers + 3 publishers + 1 subscriber listed in §3.2.6. Vulcanexus Humble base image; Fast-DDS default profile. | [`README.md`](../README.md) Interfaces section. |
| FIWARE / NGSI-LD | Four entity types managed (`Project`, `Reservation`, `Shortage`, `InventoryItem`) with JSON Schemas + `@context`. `httpx`-based client against Orion-LD; PATCH / UPSERT operations. | [`contracts/`](../contracts/) + `orion_client.py`. |
| DDS NGSI-LD mapping tool / enabler | **N/A** with documented in-process alternative path and topic ↔ entity mapping. | [`config/README.md`](../config/README.md). |
| ROS4HRI / ROS4RI | **Used — mapped, publisher implementation pending (Sprint 0.4).** The adapter will publish `hri_actions_msgs/Intent` for the **Odoo planner manufacturing-order intent**; companion nodes in `hermes_main` (extending `ar_bridge_node` for placement, plus a new companion next to `hololens_api` for project selection / assembly complete) will publish `Intent` for the HoloLens AR operator actions. Mapping reuses standard constants where they fit and domain labels otherwise — see [`D4_PLAN.md`](D4_PLAN.md) §4.4 for the full table. The message envelope is unchanged (no extension). | `02_interfaces.md` §4 + `D4_PLAN.md` §4.4. |
| Other relevant standards | **Odoo JSON-RPC** (Odoo 17 server API), **Hänel HOST-COM** (raw TCP telegrams documented in the Hänel manual), **OpenMetrics / Prometheus** (`/metrics` endpoint), **FastAPI / REST** (HTTP face). | `pyproject.toml` deps + [`README.md`](../README.md) HTTP API section. |

### 3.3.6 Demonstrated added value through the ARISE All-in-one middleware

| Question | Answer |
|---|---|
| How does the module use Vulcanexus? | Built on the official `eprosima/vulcanexus:humble` Docker image. Uses `rclpy` for the ROS 2 node, Fast-DDS as the underlying transport, and the ROS 2 message generation tooling (`rosidl_default_generators`) to build the vendored `hermes_msgs` package. |
| Which Vulcanexus / Fast-DDS-specific features are used or validated? | DDS-native single-process integration with a Python application (Fast-DDS + `rclpy` co-existing with FastAPI in one container), discovery on `ROS_DOMAIN_ID=42`, latched durability for the `/hermes/warehouse/tray_state` topic, default QoS for service/topic pairs. [TBD: any DDS Keys / Dynamic Types / Discovery Server / Easy Mode usage to enumerate.] |
| What does the module contribute back to Vulcanexus / the ARISE middleware ecosystem? | A reusable open-source pattern for embedding a FIWARE NGSI-LD bridge inside a Vulcanexus-based ROS 2 process; a working ROS 2 ↔ Odoo JSON-RPC ↔ SOAP example; a public JSON-Schema set for the four NGSI-LD entities used; a documented ROS4HRI Intent publication path for an ERP / WMS adapter. |
| Could the module become part of a Vulcanexus metapackage, tutorial set or example gallery? | Yes — proposed as a Vulcanexus *example* / *tutorial* once D4 is accepted, focusing on the "Vulcanexus + FIWARE + Industrial WMS" composition pattern. Required next step: publish a stand-alone tutorial branch with a pruned codebase (a few hundred LOC) plus a notebook walkthrough. |
| What evidence shows the contribution? | Repository, Dockerfile, mocks, schemas, this report. [TBD: PR / issue link if accepted upstream.] |
| What remains outside Vulcanexus? | The HTTP/REST face is FastAPI, not Vulcanexus / ROS 2 (intentional; the FIWARE side is REST-native). The Hänel SOAP integration is vendor-specific. The Odoo JSON-RPC is ERP-specific. |

### 3.3.7 Installation, hello world and demo evidence

| Execution element | Evidence |
|---|---|
| Installation path | Docker / Docker Compose. See §3.2.7 and [`README.md`](../README.md) Quick Start. |
| Hello world | `docker compose -f docker/docker-compose.demo.yml up`, `curl http://localhost:8080/healthz` — expected JSON `{"status":"healthy","service":"hermes-odoo-adapter","version":"2.0.0"}`. See [`docs/03_installation_and_hello_world.md`](03_installation_and_hello_world.md) for the captured output. |
| Basic demo | End-to-end Odoo MO → Orion-LD `Project` → adapter `Reservation` → ROS 2 `WarehousePick` → mock tray presentation → `ConsumeStock` → updated `InventoryItem`. [TBD: command list, expected outputs, screenshots for `docs/04_basic_demo_how_to_use.md`.] |
| Simulation / mock / recorded-data path | `NullWarehouseClient` + `docker/odoo-mock` cover the warehouse and ERP sides; Orion-LD runs as-is with Mongo. No real hardware is needed for either the hello world or the basic demo. |
| Troubleshooting | [TBD: known failure modes + diagnostic curls — Sprint 1.] |

[TBD: 1–2-paragraph narrative summarising the installation + execution evidence.]

### 3.3.8 Role in the TRL6-7 demonstrator

| Demonstrator information | Value |
|---|---|
| Demonstrator name | HERMES — ERP-driven mixed-robotics assembly cell |
| Demonstrator environment | Ampero / Olorin internal cell (Hänel MP 12N vertical lift + 2× JAKA Pro 16 cobots + XBOT AGV + Basler 4K camera on a Jetson Orin + HoloLens AR operator interface) |
| Robot / platform used | JAKA Pro 16 (×2, ASRS picking + assembly handover), XBOT AGV, Hänel MP 12N |
| End user / industrial scenario | Custom electrical-panel assembly with operator-confirmed component placement and wire routing |
| Problem addressed | Pulling customer orders from Odoo, presenting the correct trays via the Hänel, sequencing cobot picks and AGV deliveries, and tracking everything in FIWARE for the operator AR app |
| Module role in the demonstrator | The single point of integration between Odoo, FIWARE, and the ROS 2 / DDS robotics stack |
| Video link | [TBD: end-to-end demonstrator recording URL] |

| Demonstrator component | Reusable module extraction | Remaining demonstrator-specific |
|---|---|---|
| Adapter (this module) | The full Vulcanexus + FastAPI hybrid, mocks, contracts | Production Odoo instance configuration, customer BOMs, real Hänel HOST-COM credentials |
| Mission Controller | Out of scope for this module | Stays in `hermes_main` |
| Vision pipeline (Jetson) | Out of scope; consumer of `/hermes/inventory_updates` | Stays in `hermes_asrs_station` |
| HoloLens AR app | Out of scope for this module; consumer of NGSI-LD entities | Stays in `ARISE-AR-APP`; a companion ROS4HRI Intent publisher will live next to `hololens_api` (in `hermes_main`) |

### 3.3.9 Validation, impact and exploitation potential

| Evidence type | Result / link | Relevance |
|---|---|---|
| Demonstrator video | [TBD] | End-to-end use case |
| Screenshots / diagrams | [TBD: Orion entity browser, RViz topic graph, Odoo dashboard — Sprint 1.] | Visual proof of the bridging |
| Execution logs | [TBD: captured logs from a successful demo run.] | Reproducibility |
| Metrics | [TBD: latency from Odoo MO to ROS 2 service request; success rate over N runs] | Performance evidence |
| Impact on end user | [TBD: short summary from the production deployment notes.] | Industrial value |
| Impact on tech provider (reuse potential) | The adapter is reusable in any ERP-driven mixed-robotics cell that uses Vulcanexus + FIWARE. Three concrete reuse paths: (i) swap `HanelSoapClient` for another vertical-lift vendor's interface (estimated ≈300 LOC); (ii) swap Odoo for a different ERP by reimplementing `OdooClient`; (iii) use it as a Vulcanexus tutorial showing how to embed a FIWARE bridge inside a ROS 2 process. | Exploitation potential |

[TBD: 1-paragraph impact story.]

### 3.3.10 Openness, commercial boundary and limitations

| Topic | Response |
|---|---|
| Open implementation boundary | Apache-2.0 — all Python source, contracts, schemas, Dockerfiles, mocks, and the vendored `hermes_msgs` are open. |
| Commercial / proprietary elements | Production credentials for the live Hänel HOST-COM controller and Odoo instance; customer-specific BOM data; the upstream `hermes_main` Mission Controller (still internal at the time of D4 submission). |
| Technical limitations | Currently single-tenant (one Odoo + one Orion + one Hänel per adapter instance); no built-in retry of arbitrary NGSI-LD calls beyond the existing `tenacity` decorators; the ROS4HRI Intent publisher is planned for Sprint 0.4 (mapping is locked, code not yet in `ros2_node.py`); once it lands it will be unconsumed by default (no downstream node listens yet). |
| Hardware limitations | Tested only against Hänel MP 12N + JAKA Pro 16 + Vulcanexus Humble. Other vertical lifts require a `WarehouseClient` implementation. |
| Untested cases | Adapter under DDS-cross-network conditions (Discovery Server), Odoo 18, Orion-LD 1.5+ — all expected to work but not validated. |
| Future work | Sprint 0.4 — ROS4HRI Intent publisher implementation. Sprint 1.5 — fresh-machine reproducibility validation (the in-repo Docker build now resolves all dependencies; final acceptance is the clean-clone run). Demonstrator video + the eight per-stage screenshots (see `media/screenshots/README.md`). Custom QoS profile for cross-network deployments. Multi-tenant configuration. |
| Ethical / safety / privacy considerations | The adapter does not collect operator biometrics, identity, audio or video. The NGSI-LD entities it manages contain customer order ids (BOM line ids) and operator station ids; these are pseudonymous business identifiers, not personal data. Production deployments should still ensure the Orion-LD broker and Odoo instance enforce their own access controls. [TBD: confirm against the project-specific ethics report.] |

### 3.3.11 Self-assessment for ARISE ecosystem visibility

| Requested visibility level | Selection | Justification |
|---|---|---|
| Related project | Yes | Easily meets the minimum requirements once Sprint 0 + Sprint 1 are complete. |
| **Featured project** | **Yes (target)** | Strong reproducibility (Docker + mocks + vendored deps), dedicated `docs/` page set, clear demo and ARISE alignment (Vulcanexus + FIWARE + ROS4HRI Intent). |
| Flagship project | No (initial submission) | Would require: a polished demonstrator video, a Vulcanexus tutorial branch, and uptake evidence from another ARISE experiment. Plausible follow-up after Sprint 1 + a public Vulcanexus tutorial. |

| Assessment area | Evidence |
|---|---|
| Reusability | Pluggable warehouse backend; ERP client isolated behind an Odoo-specific module; the ROS 2 surface is generic. |
| Reproducibility | One-command Docker Compose demo; vendored ROS 2 messages; no private deps. |
| ARISE interoperability | Vulcanexus + FIWARE + ROS4HRI all exercised (DDS Enabler N/A justified with mapping). |
| Contribution to Vulcanexus | Reusable ERP + FIWARE + Hänel SOAP composition pattern; proposed tutorial. |
| Validation | TRL6-7 demonstrator run repeatedly in the Ampero cell. |
| Documentation quality | README, this report, `docs/D4_PLAN.md`, `config/README.md`, contracts/schemas. |
| Sustainability | Apache-2.0, single maintainer, GitHub Issues. Commercial support available via Ampero. |

### 3.3.12 Written report final checklist

- [x] Project identification table completed (placeholders for mentor + video URL).
- [x] Repository URL provided; release/tag pending Sprint 1.5 freeze.
- [x] Open implementation scope clearly described.
- [x] README and repository structure described.
- [x] ROS 2/Vulcanexus, FIWARE/NGSI-LD, DDS enabler (N/A justified) and ROS4HRI evidence summarised.
- [x] Installation, hello world and basic demo evidence included. *([`docs/03_installation_and_hello_world.md`](03_installation_and_hello_world.md) + [`docs/04_basic_demo_how_to_use.md`](04_basic_demo_how_to_use.md) + [`examples/`](../examples/) + [`launch/`](../launch/) + [`media/`](../media/).)*
- [x] TRL6-7 demonstrator role explained (placeholders for video URL + component-level mapping).
- [ ] Video and visual evidence linked. *Mermaid architecture + sequence diagrams in [`media/`](../media/) are linked from the relevant sections; the demonstrator video URL and the eight per-stage screenshots are still TBD ([`media/video_link.md`](../media/video_link.md) + [`media/screenshots/README.md`](../media/screenshots/README.md)).*
- [x] Limitations, proprietary boundaries and future work stated.
- [ ] Annexes and previous deliverables linked. *(see §3.4 below — TBD.)*

---

## 3.4 Annexes

### 3.4.1 Annex I — Previous milestones and deliverables

| Previous material | Link | Relevance to D4 |
|---|---|---|
| Stage 1 — Individual Mentoring Plan | [TBD] | Project scope / need definition |
| Stage 2 — Proof of Concept | [TBD] | Prototype reused as the v2.0 adapter |
| Stage 3 — Demonstrator (TRL6-7) | [TBD] | Validation evidence |
| Demonstrator video | [TBD] | End-to-end validation |
| Additional technical documentation | `hermes_main/docs/ASRS_SOAP_INTEGRATION_ARCHITECTURE.md`, `HERMES_SEQUENCE_DIAGRAMS.md`, `HERMES_DEVICE_INVENTORY.md` *(internal — extracts to ship with D4 if needed)* | Architecture + sequence + inventory |

**Reply to D3 evaluation recommendations:**

| Stage | Recommendation | Reply / D4 reference |
|---|---|---|
| 4 | [TBD: copy each verbatim D3 recommendation from the Evaluation Report Letter.] | [TBD: action taken + paragraph reference in this report.] |

### 3.4.2 Annex IV — Demonstrator evidence

| Evidence item | Link / description | What it demonstrates |
|---|---|---|
| Demonstrator video | [TBD] | End-to-end Odoo → ROS 2 → robot sequence |
| Architecture diagram | [`media/architecture_diagram.md`](../media/architecture_diagram.md) — Mermaid system-context diagram (renders inline on GitHub). | System context + adapter position |
| Sequence diagrams | [`media/sequence_diagram.md`](../media/sequence_diagram.md) — Mermaid diagrams for Project → Shortage, top-up → Reservation, and Mission Controller → ConsumeStock flows. | Inputs / outputs / interface logic |
| Sequence / data-flow diagram | `hermes_main/docs/HERMES_SEQUENCE_DIAGRAMS.md` (to copy or link) | Adapter inputs / outputs |
| Screenshots | [TBD — Orion entity browser, ROS 2 topic graph, Odoo dashboard, Grafana panel, Sprint 1.] | Operational behaviour |
| Metrics / test results | [TBD — capture from a clean run.] | Latency / success rate |
| End-user feedback | [TBD] | Industrial relevance |

### 3.4.3 Annex V — Commercial / proprietary clarification

| Question | Response |
|---|---|
| Which elements are open? | Adapter source, contracts, Dockerfiles, mocks, vendored `hermes_msgs`, this report. |
| Which elements are proprietary or commercial? | Live Hänel HOST-COM endpoint + credentials, production Odoo instance, customer BOMs. |
| Can the open module be executed without the proprietary elements? | **Yes.** `docker compose -f docker/docker-compose.demo.yml up` exercises the full pipeline with mocks. |
| What has been replaced by a wrapper / adapter / mock / simulation? | `NullWarehouseClient` replaces the live Hänel; `docker/odoo-mock/` replaces the live Odoo. |
| Commercial / support path beyond the open implementation? | Ampero S.r.l. offers commercial integration support for production Hänel + Odoo deployments. Contact: `francesco.solinas@olorin.tech`. |

### 3.4.4 Annex VI — Contacts and support

| Role | Name / organisation | Email / channel |
|---|---|---|
| Technical maintainer | Francesco Solinas — Ampero S.r.l. | `francesco.solinas@olorin.tech` — GitHub `@<TBD>` |
| Project coordinator / contact person | Francesco Solinas — Ampero S.r.l. | `francesco.solinas@olorin.tech` |
| Commercial contact | Ampero S.r.l. | `francesco.solinas@olorin.tech` |
| ARISE mentor | [TBD] | [TBD] |

### 3.4.4(b) Final Ethics Assessment & Roadmap for Future Use

- Project-specific ethics requirements: **[TBD — pull from the per-project report in the ARISE project folder (Part 2, question 1) and either justify or attach a short future-plan document here.]**
- Roadmap for future use: **[TBD — compile via a team session using the ARISE foresight template; capture what we want the adapter to contribute to, what to avoid, and the decisions / considerations relevant in the years ahead.]**
- Compiled Roadmap document link: [TBD]

---

## Submission readiness summary

| Section | Skeleton complete | Real content complete |
|---|---|---|
| 3.1 Identification | ✅ | ⚠️ mentor + video URL TBD |
| 3.2.1 – 3.2.4 Repo identification / license / scope / structure | ✅ | ✅ |
| 3.2.5 README content | ✅ | ⚠️ ARISE narrative + capabilities table TBD (Sprint 2) |
| 3.2.6 Interfaces | ✅ | ⚠️ ROS4HRI Intent publisher TBD (Sprint 0.4); examples TBD (Sprint 1) |
| 3.2.7 Install / hello world / demo | ✅ | ⚠️ Sprint 1 + 1.5 |
| 3.2.8 Repo evidence checklist | ✅ | ⚠️ depends on the above |
| 3.3.1 – 3.3.10 Written report | ✅ | ⚠️ several `[TBD]` blocks (annex links, demonstrator video, Vulcanexus PR/issue) |
| 3.3.11 Self-assessment | ✅ | ✅ (Featured target stated) |
| 3.3.12 Written report final checklist | ✅ | ⚠️ depends on the above |
| 3.4 Annexes | ✅ | ⚠️ all `[TBD]` |

Roughly **half** of the report is fully populated; the rest is a tractable
list of `[TBD]` items, each pointing at the sprint that produces the
evidence (see `D4_PLAN.md`).
