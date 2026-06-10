# D4 — Shareable HRI Module: Status & Plan

Source: `D4 - Shareable HRI Modules.docx` (ARISE FSTP Stage 4 template).
Our module: **HERMES Odoo Adapter** — a Vulcanexus/ROS 2 + FastAPI hybrid that
bridges Odoo (JSON-RPC), Orion-LD (NGSI-LD) and the Hänel ASRS (SOAP) and
exposes a clean ROS 2 service layer to the Mission Controller.

Repo: <https://github.com/Ampero-SRL/hermes-odoo-adapter> (branch `main`).
Last updated: 2026-05-27 (codex-reviewed).

> **Codex review (2026-05-27).** Codex flagged five things I missed or got
> wrong; they are folded into the plan below — calling them out here for
> visibility:
>
> 1. **Stability target is 2033-06-30**, not 2027-06-30 (6 years *after*
>    ARISE ends on 2027-06-30). The submitted tag must remain stable until
>    then.
> 2. **External-dependency list is mandatory.** Our adapter imports
>    `hermes_msgs`, which lives outside this repo — a fresh reviewer
>    cannot reproduce hello world today. Vendoring or pinning it is the
>    single biggest packaging risk.
> 3. **README ↔ code drift.** README advertises six ROS 2 services and
>    `/hermes/articles/push`, but `ros2_node.py` exposes five and the
>    `PushArticle` service was removed. Fix repo truth *before* writing
>    `02_interfaces.md`.
> 4. **Sequence the decisions first.** Decide DDS-enabler-vs-custom-bridge
>    and the ROS4HRI position *before* writing the interface doc; otherwise
>    we rewrite the most-scrutinized page.
> 5. **The riskiest single item is a fresh-machine reproducibility path** —
>    clone repo → docker compose up → one curl + one `ros2 service call`
>    → expected output, with **no** dependency on `hermes_main`, real Hänel
>    or local workspace state. Codex was emphatic: nail this first; the
>    rest is doc polish.
>
> **Codex round 2 (2026-05-27, after the ROS4HRI flip).** Five more corrections
> folded in below:
>
> - **Repo isn't self-contained today** — the Dockerfile copies `hermes_main`
>   and `pyproject.toml` has placeholder metadata, so the adapter repo
>   alone is *not yet a valid D4 artifact*. Promoted to **Sprint 0 item #1**
>   (gates everything else).
> - **The adapter is Poetry/FastAPI, not a colcon package** — so "add to
>   `package.xml`" wasn't actionable as I wrote it. Use a `.repos` /
>   `vcs-import` or Docker-stage pattern for `hermes_msgs` and
>   `hri_actions_msgs`.
> - **Narrow the ROS4HRI claim:** only `START_ACTIVITY` is a strong fit;
>   `PLACE_OBJECT` / `STOP_ACTIVITY` would over-claim. Use domain labels
>   `CONFIRM_PLACEMENT` and `COMPLETE_ACTIVITY` for the two operator
>   confirmations (mapping table in §4.4 updated).
> - **Publisher should live closest to the source**, not inside the adapter:
>   `ar_bridge_node` (ROS 2, already receives placement HTTP) for placement,
>   a small companion next to `hololens_api` (FastAPI today) for
>   project_selected / assembly_complete. The adapter only publishes the
>   Odoo-MO planner-derived intent.
> - Remaining riskiest items beyond reproducibility: dependency packaging
>   for `hri_actions_msgs`, the multi-repo boundary, the DDS enabler
>   decision, placeholder `pyproject.toml`, and concrete video / screenshot
>   / annex evidence.
>
> **ROS4HRI position (revised after verifying the upstream `Intent.msg`).** I
> originally planned N/A. Verifying [`ros4hri/hri_actions_msgs`](https://github.com/ros4hri/hri_actions_msgs/blob/humble-devel/msg/Intent.msg)
> showed the fit is much better: the AR operator / Odoo planner inbound
> flows are *literal* ROS4HRI intents and several map directly onto
> existing standard constants (`START_ACTIVITY` ↔ project_selected,
> `PLACE_OBJECT` ↔ confirm_placement, `STOP_ACTIVITY` ↔ assembly_complete,
> with `source=REMOTE_SUPERVISOR`, `modality=MODALITY_TOUCHSCREEN`). So
> the alignment is **"Used"** — no message extension, ~30 LOC of publisher
> + doc page. The full mapping table is in §4.4.

---

## 1. What ARISE asks for (executive)

ARISE wants a **reusable** open implementation of at least one capability from
our TRL6-7 demonstrator, with:

- an **open GitHub repo** (LICENSE, README, docs, examples, install path);
- **documented interfaces** to ROS 2/Vulcanexus, FIWARE/NGSI-LD, DDS-NGSI-LD
  enabler, and ROS4HRI/ROS4RI (or a justified N/A);
- a **Hello World** path that runs without the original industrial hardware
  (mocks, bag files, simulation accepted);
- a **basic demo** with expected output + visual evidence;
- a written **8–15 page report** plus annexes (previous milestones, demonstrator
  evidence, commercial boundary, contacts, ethics/roadmap).

A reviewer must understand, in **under 10 min**: what the module solves, which
platforms it helps, missions/tasks, off-the-shelf capabilities, install + run,
ARISE alignment, role in the demonstrator, and what is ad hoc / proprietary /
future work.

---

## 2. Master checklist — status

Status legend: ✅ done · ⚠️ partial · ❌ missing.
Citations are paths relative to the `hermes_odoo_adapter/` repo unless noted.

### 2.1 Repository basics (D4 §2.3 + §3.2.4)

| # | Item | Status | Evidence / Gap |
|---|---|---|---|
| 1 | GitHub repo accessible | ✅ | github.com/Ampero-SRL/hermes-odoo-adapter |
| 2 | Open base implementation | ✅ | `src/hermes_odoo_adapter/` (Python) |
| 3 | LICENSE | ✅ | `LICENSE` (Apache-2.0 by size) + `NOTICE` |
| 4 | README complete | ⚠️ | `README.md` covers arch / ROS2 / HTTP API / NGSI-LD; **missing**: ARISE connection narrative, target-platforms table, missions/tasks mapping, off-the-shelf capabilities table, limitations, maintainer block, demo vs. hello-world split |
| 5 | `docs/` folder | ✅ | Five D4-recommended pages (`docs/01_arise_context.md` → `docs/05_role_in_demonstrator.md`) plus the D4 plan + report draft and an interfaces / install / demo set |
| 6 | `examples/` folder | ✅ | `examples/{payloads,curl,ros2}/` with runnable scripts driving the demo compose; payloads use the real seeded mock SKUs (`SCH-REL-24V`, `ABB-MCB-10A`, …) and the `DEMO-CTRL` project from `project_mapping.json` |
| 7 | `launch/` folder | ✅ | `launch/hermes_odoo_adapter.launch.py` — thin `ExecuteProcess` wrapper so `ros2 launch hermes_odoo_adapter hermes_odoo_adapter.launch.py` works alongside the existing `python -m` / Docker entrypoints. Declares `ros2_node_name` / `warehouse_backend` / `log_level` / `extra_env`. See `launch/README.md` |
| 8 | `config/` folder | ⚠️ | Settings via `.env` / `.env.example`; `config/README.md` documents the FIWARE DDS Enabler as N/A with the canonical topic↔entity mapping (no enabler config file shipped) |
| 9 | `media/` folder | ⚠️ | Mermaid `architecture_diagram.md` + `sequence_diagram.md` are in place + the `video_link.md` + `screenshots/README.md` shot-list scaffold. **Pending**: the actual demonstrator video URL and the eight per-stage screenshots — captured during the live demo, tracked in Sprint 1 backlog |
| 10 | `docker/` or `docker-compose.yml` | ✅ | `Dockerfile`, `docker/docker-compose.full.yml`, `docker/docker-compose.demo.yml` |
| 11 | Tests | ✅ | `tests/unit/`, `tests/integration/`, `pytest.ini` |

### 2.2 Interfaces (D4 §3.2.6 — required interoperability evidence)

| # | Item | Status | Evidence / Gap |
|---|---|---|---|
| 12 | ROS 2/Vulcanexus interfaces documented | ⚠️ | README "ROS2 Interfaces" lists services + topics + examples; **missing**: nodes/actions/params, QoS settings, launch files, dedicated `docs/02_interfaces.md` table |
| 13 | FIWARE / NGSI-LD interface (entities + @context + payload examples) | ✅ | `contracts/schemas/{Project,Reservation,InventoryItem,Shortage}.schema.json` + `contracts/context/context.jsonld` + README "NGSI-LD Entities"; **add** payload examples + Context Broker walkthrough |
| 14 | DDS NGSI-LD integration (DDS enabler conf file) | ❌ | No `config/dds_enabler.*` shipped; document whether enabler used or justify N/A and describe the alternative integration path |
| 15 | ROS4HRI / ROS4RI alignment | ⚠️ | **Decision flipped from N/A → Used.** Publish `hri_actions_msgs/Intent` for operator / planner inbound flows. **Mapping (narrowed after codex round 2):** `START_ACTIVITY` (standard) for project_selected; domain labels `CONFIRM_PLACEMENT` and `COMPLETE_ACTIVITY` for the two operator confirmations (do *not* over-claim `PLACE_OBJECT` / `STOP_ACTIVITY` — upstream semantics differ); `REMOTE_SUPERVISOR` / `MODALITY_TOUCHSCREEN` for AR. Publisher lives in `ar_bridge_node` (placement) and a small companion node next to `hololens_api` (project/complete) — *not* the adapter, except for the Odoo-MO intent. See §4.4. |
| 16 | Vulcanexus-specific features used | ⚠️ | Uses Fast-DDS via Vulcanexus; **document**: ROS 2 distro/version, DDS Keys, XTypes / Dynamic Types, QoS, Discovery Server / Easy Mode, transports, DDS Enabler |

### 2.3 Install / Hello World / Demo (D4 §3.2.7)

| # | Item | Status | Evidence / Gap |
|---|---|---|---|
| 17 | Software dependencies listed | ✅ | `pyproject.toml` + `poetry.lock` + Dockerfile |
| 18 | Hardware dependencies listed | ⚠️ | README mentions Hänel MP and JAKA cell; **add** a single table separating *hello world* deps (none) vs. *full demo* deps (real Hanel/JAKA) |
| 19 | Simulation / mock path available | ✅ | `NullWarehouseClient` + `docker-compose.demo.yml` + seeds (`seed_orion_demo.py`, `seed_odoo_demo.py`) |
| 20 | Hello world works | ⚠️ | Quick-start exists; **need** a clearly labelled "Hello World" with exact command + expected log output (single curl + ROS 2 service call) |
| 21 | Basic demo documented | ⚠️ | Quick-start covers it implicitly; **need** a "Basic demo" section with scenario + commands + expected outputs + screenshots |

### 2.4 Written report (D4 §3.3) and annexes (§3.4)

| # | Item | Status | Evidence / Gap |
|---|---|---|---|
| 22 | D4 written report (8–15 pages) | ❌ | Not started — fill the template in `D4 - Shareable HRI Modules.docx` |
| 23 | Project identification sheet (§3.1) | ❌ | Fill: title, acronym, lead org, contacts, mentor, module name, repo URL, release tag, demo video URL |
| 24 | Repo identification & access (§3.2.1) | ⚠️ | Repo public ✅ but need a tagged release (e.g. `v0.4.0-d4`) frozen until **2033-06-30** (6 years after ARISE ends 2027-06-30) |
| 24a | External-dependency manifest (§3.2.1) | ❌ | List external private repos / binaries / datasets / docker registries / hardware drivers needed for the minimum example. Today the adapter imports `hermes_msgs` from outside this repo — a fresh reviewer can't reproduce; must vendor or pin (see §3 Sprint 0) |
| 24b | README ↔ code drift | ❌ | README claims six services + `/hermes/articles/push`; `ros2_node.py` exposes five and `PushArticle` was removed. Fix before writing interface docs |
| 24c | D3 evaluation recommendations reply (§3.4.1) | ❌ | Hard checklist: copy each received recommendation verbatim and either answer it or point to the D4 paragraph that addresses it |
| 24d | Other interoperability standards (§3.3.5 "Other") | ❌ | Name Odoo JSON-RPC, Hänel SOAP/HOST-COM, Prometheus/OpenMetrics, FastAPI/REST — D4 explicitly invites them under "Other relevant standard/interface" |
| 25 | License / ownership / maintainership (§3.2.2) | ⚠️ | LICENSE present; **add** copyright owner block, third-party licenses summary (NOTICE has some), maintainer contact, maintenance commitment, commercial/proprietary boundary statement |
| 26 | Scope of open implementation (§3.2.3) | ❌ | Capability-by-capability table: what is open / wrapper / mock / proprietary |
| 27 | Off-the-shelf capabilities (§3.3.4) | ❌ | Table: capability → input → output → interface → status |
| 28 | Platforms / missions / tasks (§3.3.3) | ❌ | Tested platforms table + mission contribution table + task I/O table |
| 29 | Role in TRL6-7 demonstrator (§3.3.8) | ❌ | Map adapter → demonstrator components + what is demonstrator-specific |
| 30 | Validation / impact / exploitation (§3.3.9) | ❌ | Metrics, screenshots, end-user feedback, reuse potential |
| 31 | Openness / commercial boundary / limitations (§3.3.10) | ❌ | Explicit known limits + future work |
| 32 | Self-assessment (§3.3.11) | ❌ | Choose Related / Featured / Flagship and justify |
| 33 | Annex I: previous milestones links (§3.4.1) | ❌ | Stage 1 / Stage 2 / Stage 3 deliverable + demonstrator video URLs |
| 34 | Annex IV: demonstrator evidence (§3.4.2) | ❌ | Demo video, architecture diagram, sequence diagram, screenshots, metrics, end-user feedback |
| 35 | Annex V: commercial / proprietary clarification (§3.4.3) | ❌ | Optional but recommended given Hanel SOAP + Odoo specifics |
| 36 | Annex VI: contacts (§3.4.4) | ❌ | Maintainer, coordinator, commercial, ARISE mentor |
| 37 | Annex VI(b): Final Ethics Assessment & Roadmap | ❌ | Per-project requirements + roadmap template to fill |
| 38 | D3 evaluation recommendations reply | ❌ | Copy received recommendations + reply or point to D4 paragraph |

---

## 3. Plan — concrete actions

Ranked by priority and grouped by deliverable area. Effort is rough person-days
for the maintainer (single dev pace).

### Sprint 0 — sequence the irreversible decisions FIRST (per codex, 0.5 day)

These items rewrite later docs (and risk a non-submittable repo) if we get them
wrong, so do them up front. **Order per codex's second-round review:**

1. **Define the submitted-repo boundary; make the adapter build from a clean
   clone.** *(the single highest priority — without this the repo is not a
   valid D4 artifact, per codex)*
   - **Vendor or fetch `hermes_msgs`**: the adapter imports it, and the
     current `Dockerfile` builds from the parent `ARISE/` directory and
     copies `hermes_main` (verified by codex). For D4 the adapter repo must
     be self-contained from a clean `git clone`. Options: vendor a minimal
     `ros2_ws/src/hermes_msgs` in this repo, or use a `.repos`/`vcs-import`
     file pinning a tagged `hermes_main` commit, or have the Dockerfile
     `git clone` it at build time.
   - **Add the `hri_actions_msgs` dependency path**: since the adapter is
     Poetry/FastAPI (not a colcon package — codex noted this; no
     `package.xml` exists), we **can't** "add to package.xml" as I wrote
     earlier. Use the same `.repos` / Docker-stage pattern as `hermes_msgs`,
     or add a tiny colcon wrapper for the ROS-message dependencies only.
   - **Fix `pyproject.toml` metadata**: replace any placeholder repo URL /
     authors / description with real values; ensure `name`, `version`,
     `homepage`, `repository` point at the public repo.
   - **Rewrite Dockerfile to build from the adapter repo alone** (the
     `git clone hermes-odoo-adapter && docker compose up` path of Sprint 1.5
     must work).
   *(1 d — gates everything else)*
2. **Decide DDS-enabler-vs-custom-bridge.** If we ship the FIWARE DDS enabler,
   place its config at `config/dds_enabler.yaml` and treat it as the
   integration path. If we keep our own `orion_client` as the bridge, write
   `config/README.md` with an explicit N/A + the topic↔entity mapping
   table. *(0.25 d)*
3. **Decide the ROS4HRI Intent publisher topology** (NEW per codex, point 4):
   - For HoloLens AR operator flows (`project_selected`,
     `placement_confirmed`, `assembly_complete`), publish **closest to the
     source**, not from the adapter — the adapter only learns of these
     events second-hand. Two clean options: (a) extend `ar_bridge_node` (a
     ROS 2 node that already receives placement HTTP) to also publish the
     Intent; or (b) add a small companion `operator_intent_bridge` rclpy
     node next to `hololens_api` (which is FastAPI today). Pick one.
   - The **adapter** itself publishes only **planner-derived intents** from
     the Odoo poll loop (the MO → `FULFILL_KIT`/`START_ACTIVITY`). That's a
     much smaller change scope.
   - Topic placeholder: `/humans/intents` (mentor confirms).
   *(0.25 d to design; impl in step 4 below)*
4. **Implement the Intent publisher(s)** per the topology decided in step 3,
   with the narrowed mapping in §4.4 (`START_ACTIVITY` standard, plus
   domain labels `CONFIRM_PLACEMENT` and `COMPLETE_ACTIVITY` — *not*
   `PLACE_OBJECT` / `STOP_ACTIVITY`, which would overclaim). A minimal test
   that one Intent fires per call. *(0.5 d)*
5. **Fix repo truth**: README claims 6 services + `/hermes/articles/push`;
   reconcile with `ros2_node.py` (5 services; `PushArticle` removed). Update
   README. *(no extra cost; must precede `02_interfaces.md`)*
6. **Start the D4 written-report skeleton in parallel** — filling §3.1–§3.4
   tables exposes missing evidence earlier than prose docs do. *(0.5 d)*

### Sprint 1 — repository hygiene (2–3 days)

1. *(Tag at the end of the plan, not here.)* The D4 tag `v0.4.0-d4` is cut **only after** a fresh-machine/fresh-container hello world passes (Sprint 1.5).
2. **Create `docs/` folder** with the five files D4 recommends:
   - `01_arise_context.md` — why the adapter exists, the HRI / industrial story, link to ARISE All-in-one middleware concepts. *(0.5 d)*
   - `02_interfaces.md` — formal ROS 2 (nodes/topics/services/actions/params/QoS/launch) + FIWARE/NGSI-LD (entity tables, @context, payload examples, Context Broker walkthrough) + DDS enabler config (or explicit N/A + alternative path) + **ROS4HRI alignment table from §4.4 (Used — Intent publisher, with the narrowed standard-vs-domain label mapping)**. *(1 d)*
   - `03_installation_and_hello_world.md` — split clearly from the basic demo: a one-page "install + 1 curl + 1 ros2 service call → expected output". *(0.5 d)*
   - `04_basic_demo_how_to_use.md` — end-to-end Odoo→Orion→ROS 2 walkthrough using the demo compose + seeds, with expected outputs and 3–4 screenshots. *(0.5 d)*
   - `05_role_in_demonstrator.md` — map adapter to the HERMES TRL6-7 demonstrator and what remains demonstrator-specific. *(0.5 d)*
3. **Create `media/`** with: architecture diagram (PNG + SVG), sequence diagram (reuse `hermes_main/docs/HERMES_SEQUENCE_DIAGRAMS.md` figures), 3 screenshots (Orion entities, RViz/ROS 2 topic graph, Odoo dashboard), `video_link.md`. *(0.5 d)*
4. **Create `examples/`** with: `examples/payloads/` (NGSI-LD Project, Reservation, Shortage), `examples/curl/` (HTTP API end-to-end), `examples/ros2/` (service call scripts), `examples/bagfiles/` (optional). *(0.5 d)*
5. **Create `launch/`** with a minimal `hermes_odoo_adapter.launch.py` (ROS 2 launch wrapping the current entry point) so ARISE can run `ros2 launch …`. *(0.5 d)*
6. **`config/dds_enabler.yaml`** — ship the enabler conf or, if not used, add `config/README.md` justifying N/A with the alternative integration path. *(0.5 d)*

### Sprint 2 — README rewrite to D4 §3.2.5 structure (1 day)

Sections required:
- Module introduction (name, problem, inputs, outputs, capability) ✅ partial
- Connection with ARISE (Vulcanexus, FIWARE/NGSI-LD, DDS, ROS4HRI) ❌ add
- Target platforms (tested / expected / unsupported tables) ❌ add
- Robot missions and tasks (table) ❌ add
- Off-the-shelf capabilities (table) ❌ add
- Quick start ✅ rephrase as **Hello World** + link to docs
- Basic demo ⚠️ link to `docs/04_basic_demo_how_to_use.md`
- Limitations ❌ add (with explicit untested + proprietary boundary)
- Citation / contact ❌ add

### Sprint 3 — the written report (3–4 days)

Fill the §3.1–§3.4 tables of the D4 template using the docs/ pages as the
technical backing. Concretely:

- 3.1 Identification sheet — fill once Sprint 1 release is tagged.
- 3.2 GitHub repository tables — point to docs/, contracts/, examples/, media/.
- 3.3 Written report sections — each table maps 1:1 to a doc page.
- 3.4 Annexes — link previous deliverables, attach video + architecture
  diagram + sequence diagram, fill the commercial/proprietary boundary
  (Hänel SOAP is vendor-specific; Odoo addon scope is documented).

Key narratives to write:
- **ARISE alignment narrative** (§3.3.2): how the adapter pulls Odoo BOMs into
  NGSI-LD `Reservation` entities, drives ROS 2 services to the Mission
  Controller, and surfaces ASRS state via NGSI-LD `Shortage`.
- **Added value through Vulcanexus** (§3.3.6): single-process node hosting,
  Fast-DDS QoS, NGSI-LD ↔ DDS data-model alignment, how it could ship as a
  Vulcanexus tutorial / example.
- **Impact story** (§3.3.9): how the adapter unlocks the "warehouse hand-off
  to cobot" capability the demonstrator validated, and who else can reuse it
  (any ERP-driven mixed-robotics cell).

### Sprint 1.5 — fresh-reviewer reproducibility path (the riskiest item, 1 day)

Codex's verdict: nail this **before** any media polish or tag.

Acceptance criteria: a clean machine (or a fresh container) can run, from
the adapter repo alone, **without** `hermes_main`, real Hänel or local
workspace state:

```
git clone https://github.com/Ampero-SRL/hermes-odoo-adapter
cd hermes-odoo-adapter
docker compose -f docker/docker-compose.demo.yml up -d
curl -s http://localhost:8080/healthz
curl -s http://localhost:8080/api/v1/projects   # or one NGSI-LD seed
ros2 service call /hermes/warehouse/pick hermes_msgs/srv/WarehousePick "{...}"
# → expected JSON / log lines documented in docs/03_installation_and_hello_world.md
```

Pin Docker tags. Capture the exact expected output. **The ROS 2 call must
work against `NullWarehouseClient`**, not the real Hänel.

### 4.4 ROS4HRI alignment — VERIFIED from upstream (no extension needed)

Verified directly against [`ros4hri/hri_actions_msgs/msg/Intent.msg`](https://github.com/ros4hri/hri_actions_msgs/blob/humble-devel/msg/Intent.msg) on the `humble-devel` branch.

**The fit is much better than I first thought.** Several of our operator /
planner inbound flows map *cleanly* to the existing `Intent.intent` constants —
no message extension, and only a couple of domain-specific labels at all.

`Intent.msg` fields (all standard):
- `intent` (string, with predefined constants: `RAW_USER_INPUT`, `ENGAGE_WITH`,
  `MOVE_TO`, `GUIDE`, `GRAB_OBJECT`, `BRING_OBJECT`, `PLACE_OBJECT`, `GREET`,
  `SAY`, `PRESENT_CONTENT`, `PERFORM_MOTION`, `START_ACTIVITY`, `STOP_ACTIVITY`,
  `WAKEUP`, `SUSPEND` — the field is a string, so domain labels are allowed)
- `data` (string, JSON — thematic roles: agent / object / goal / recipient)
- `source` (string, with `ROBOT_ITSELF`, `REMOTE_SUPERVISOR`, `UNKNOWN_AGENT`, `UNKNOWN`)
- `modality` (`MODALITY_SPEECH`, `MODALITY_MOTION`, `MODALITY_TOUCHSCREEN`,
  `MODALITY_OTHER`, `MODALITY_INTERNAL`)
- `priority` (uint8, default 128), `confidence` (float32 0..1)

**Mapping table for §3.2.6 of the D4 report (HRI concept | module representation | alignment | evidence):**

| Adapter flow (today) | `Intent.intent` | `source` | `modality` | `data` (JSON) | Alignment |
|---|---|---|---|---|---|
| HoloLens "select project" → `notify_hermes_project_selected` | `START_ACTIVITY` | `REMOTE_SUPERVISOR` | `MODALITY_TOUCHSCREEN` | `{"activity":"assembly","project_id":..., "operator_id":...}` | **Used — standard constant (strong fit)** |
| HoloLens "confirm placement" → `notify_ar_bridge_placement_confirmed` | `CONFIRM_PLACEMENT` *(domain string)* | `REMOTE_SUPERVISOR` | `MODALITY_TOUCHSCREEN` | `{"agent":"operator", "object":"<component>","goal":"<slot>"}` | **Used — domain label** (only use `PLACE_OBJECT` if framed strictly as "operator declares they placed object X at slot Y"; otherwise the upstream semantics are about commanding the robot to place, not the operator confirming, so a custom label is safer) |
| HoloLens "assembly complete" → `notify_hermes_assembly_complete` | `COMPLETE_ACTIVITY` *(domain string)* | `REMOTE_SUPERVISOR` | `MODALITY_TOUCHSCREEN` | `{"activity":"assembly","project_id":..., "status":"complete"}` | **Used — domain label** (do **not** use `STOP_ACTIVITY` — codex flagged that upstream semantics are cancellation/abort, not normal completion) |
| Odoo planner places MO → adapter polls + creates `Reservation` | `START_ACTIVITY` *(or domain `FULFILL_KIT`)* | `REMOTE_SUPERVISOR` *(or `UNKNOWN_AGENT` if no Odoo user known)* | `MODALITY_OTHER` | `{"activity":"manufacturing_order","mo_id":..., "bom":...}` | **Used — standard constant** |
| Operator "ack shortage" (future) | `RAW_USER_INPUT` *or domain `ACK_SHORTAGE`* | `REMOTE_SUPERVISOR` | `MODALITY_TOUCHSCREEN` | `{"shortage_id":...}` | **Used — domain label** |

**Honest framing for the report (per codex second-check):** of the four flows
we publish, only `START_ACTIVITY` is a clean fit to an upstream constant.
The other two operator confirmations and the MO are documented as
domain-specific intent strings carried by the standard `Intent` message
envelope — which the ROS4HRI spec explicitly allows. This is still
"Used", not "Extension" (the message schema is unchanged), but the report
should not over-claim semantic equivalence where it doesn't hold.

So the alignment claim for D4 §3.3.5 is straightforwardly **"Used — the adapter
publishes `hri_actions_msgs/Intent` for every operator / planner inbound flow,
re-using the standard `intent` / `source` / `modality` constants where they fit
and adding domain-specific string labels (no message extension) where they
don't."** Strictly stronger than "N/A with thin angle."

**Implementation cost** (now a real Sprint 0 task, not Sprint 4 write-up):
- New ROS 2 publisher in `ros2_node.py` on topic `/humans/intents` (need to
  confirm topic name with mentor; some PAL examples use `/intents`).
- A small `_publish_intent(intent: str, source: str, modality: str, data: dict, confidence: float = 1.0)` helper.
- Call sites: the four `notify_*` functions in `panelserver/app.py` (those are
  in the AR repo, not the adapter — so the adapter side is just the Odoo poll
  loop) **plus** the existing AR-bridge / Hermes API endpoints that receive
  the operator notifications in `hermes_main/hololens_api/app/main.py` should
  fan out an Intent publish too (single place; the adapter listens or the
  bridge publishes — to decide).
- `package.xml` dep on `hri_actions_msgs` (apt: `ros-humble-hri-actions-msgs`
  when published, otherwise vcs-import from source).
- Estimated ~30 LOC + a doc page (`docs/02_interfaces.md` ROS4HRI section).

**Open mentor questions** (small, write-up only):
1. Canonical topic name for the Intent stream — `/intents`, `/humans/intents`,
   or domain-namespaced `/hermes/operator/intents`?
2. For `source` of the AR operator: keep `REMOTE_SUPERVISOR` (standard) or
   use a richer string `operator/<headset_id>`? Standard says strings allowed
   alongside the constants.
3. For an MO without an Odoo user attribution: `REMOTE_SUPERVISOR` vs
   `UNKNOWN_AGENT` — leans `REMOTE_SUPERVISOR` ("the planning system is the
   remote supervisor of the cell").

### Sprint 4 — DDS-enabler write-up (0.25 day, after Sprint 0 decisions)

DDS enabler: confirm whether the production deployment uses the FIWARE DDS
enabler (`ngsild2dds`) or our own bridge code is the integration path; if our
own, write `config/README.md` with an explicit N/A + topic-to-entity mapping
so a third party could swap in the enabler. (The ROS4HRI write-up moved into
`02_interfaces.md` per §4.4; no separate sprint needed.)

DDS enabler: confirm whether the production deployment uses the FIWARE DDS
enabler (`ngsild2dds`) or our own bridge code is the integration path; if our
own, include a short doc explaining how a third party could swap in the
enabler for the same topics → entities mapping.

### Sprint 5 — ethics + roadmap (1 day)

Pull the project-specific report (Part 2, question 1) from the project folder
and draft the future-use roadmap with the team. Compile both into the report
links (Annex VI).

### Cross-cutting hygiene (parallel, 1 day)

- Add a `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` (GitHub will
  surface them as the project becomes Featured/Flagship).
- Enable Issues + a `bug` / `enhancement` template under `.github/`.
- Confirm public visibility now, freeze the D4 tag, and capture the demo video
  link from `hermes_main/docs/`.

---

## 4. Risk / open questions (need a decision)

- **Visibility level** to claim in §3.3.11: aim for **Featured** for D4
  submission, lift to **Flagship** later if the demonstrator video + a
  Vulcanexus tutorial land.
- **ROS4HRI Intent publisher** — confirm with mentor: (a) topic name (`/humans/intents` vs `/intents` vs domain), (b) acceptance of custom intent labels (`CONFIRM_PLACEMENT`, `COMPLETE_ACTIVITY`) alongside standard ones, (c) which node publishes (extend `ar_bridge_node` vs new companion next to `hololens_api`).
- **DDS enabler vs. custom bridge** — pick one and document, do not mix.
- **Demonstrator video** — confirm there is a recording suitable for ARISE
  review (end-to-end Odoo → Orion → ROS 2 → robot). If not, schedule a 5-min
  recording before tagging the release.

---

## 5. References

- D4 template (this folder's source): `/home/parallels/Desktop/ARISE/D4 - Shareable HRI Modules.docx`
- Main architecture doc: `hermes_main/docs/ASRS_SOAP_INTEGRATION_ARCHITECTURE.md`
- Sequence diagrams: `hermes_main/docs/HERMES_SEQUENCE_DIAGRAMS.md`
- Device inventory: `hermes_main/docs/HERMES_DEVICE_INVENTORY.md`
- ARISE checklist mirror: §2.3 of the D4 docx (24 items) — items mapped above.
