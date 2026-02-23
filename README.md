# HERMES Odoo Adapter v2.0

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![ROS2](https://img.shields.io/badge/ROS2-Humble-blue.svg)](https://docs.ros.org/en/humble/)
[![Vulcanexus](https://img.shields.io/badge/Vulcanexus-Humble-orange.svg)](https://vulcanexus.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docs.docker.com/compose/)

A **hybrid ROS2 + FastAPI adapter** that bridges **Odoo ERP**, **FIWARE Context Brokers**, and **warehouse systems** (Hanel vertical lifts via SOAP) for smart manufacturing in the HERMES/ARISE project. Built on **Vulcanexus Humble** (eProsima Fast-DDS) for native DDS communication.

## Key Features

- **4-Protocol Hub**: Speaks DDS (ROS2/Vulcanexus), JSON-RPC (Odoo), NGSI-LD (FIWARE), and SOAP 1.1 (Hanel warehouse) from a single process
- **ROS2 Services**: Exposes warehouse pick, stock consume/produce, and article push operations as ROS2 services over Fast-DDS
- **Warehouse Abstraction**: Pluggable backend — `HanelSoapClient` for production SOAP integration, `NullWarehouseClient` for dev/test (replaces WireMock)
- **Real-time Project Processing**: Processes manufacturing projects from NGSI-LD notifications
- **BOM Resolution**: Resolves Bills of Materials and checks component availability via Odoo
- **Bidirectional Stock Operations**: Read inventory levels AND write stock changes during missions
- **Inventory Sync**: Continuous sync between Odoo, warehouse, and FIWARE context
- **Warehouse Sync**: Article bootstrap, inbound stock detection, and inventory reconciliation with Hanel
- **Mission State Bridge**: Subscribes to `/hermes/mission_state` ROS2 topic and patches FIWARE entities (absorbs ROS-FIWARE Bridge)
- **Production Ready**: Circuit breakers, retry logic, Prometheus metrics, structured logging
- **Docker-First**: Vulcanexus Humble base image with multi-stage build

## Architecture

The adapter acts as the central hub — one process, four protocols:

```
                         ROS2 DDS (Fast-DDS / Vulcanexus)
                    ┌──────────────┴──────────────┐
                    │                              │
                    ▼                              │
          ┌─────────────────────────────────────────────────────┐
          │            HERMES ODOO ADAPTER v2.0                 │
          │            (FastAPI + rclpy hybrid)                  │
          │                                                     │
          │  ROS2 FACE (DDS)              FastAPI FACE (:8080)  │
          │                                                     │
          │  Services:                    GET  /healthz          │
          │   /hermes/warehouse/pick      GET  /readyz           │
          │   /hermes/warehouse/status    GET  /metrics          │
          │   /hermes/warehouse/cancel    POST /orion/notify     │
          │   /hermes/stock/consume       POST /api/consume      │
          │   /hermes/stock/produce       POST /api/produce      │
          │   /hermes/articles/push       GET  /admin/...        │
          │                                                     │
          │  Topics:                                            │
          │   /hermes/inventory_updates (pub)                   │
          │   /hermes/mission_state (sub)                       │
          │                                                     │
          │  ┌───────────┐  ┌───────────┐  ┌─────────────────┐ │
          │  │ Odoo      │  │ Orion     │  │ Warehouse       │ │
          │  │ Client    │  │ Client    │  │ Client          │ │
          │  │ (JSONRPC) │  │ (NGSILD)  │  │ ┌─────────────┐ │ │
          │  │           │  │           │  │ │ HanelSoap   │ │ │
          │  │           │  │           │  │ │ (SOAP 1.1)  │ │ │
          │  │           │  │           │  │ ├─────────────┤ │ │
          │  │           │  │           │  │ │ NullClient  │ │ │
          │  │           │  │           │  │ │ (dev/test)  │ │ │
          │  │           │  │           │  │ └─────────────┘ │ │
          │  └─────┬─────┘  └─────┬─────┘  └───────┬─────────┘ │
          └────────┼──────────────┼─────────────────┼───────────┘
                   │              │                  │
                JSON-RPC       NGSI-LD            SOAP 1.1
                   ▼              ▼                  ▼
             ┌──────────┐  ┌──────────┐      ┌──────────────┐
             │ Odoo ERP │  │ Orion-LD │      │  Hanel MP    │
             └──────────┘  └──────────┘      │  Controller  │
                                             └──────────────┘
```

### Key Components

- **HermesAdapterNode** (`ros2_node.py`): ROS2 node with 6 service servers, 1 publisher, 1 subscriber — runs in a background thread alongside FastAPI
- **WarehouseClient** (`warehouse/`): Abstract interface with `HanelSoapClient` (zeep-based SOAP 1.1) and `NullWarehouseClient` (dev stub)
- **WarehouseSyncWorker** (`workers/warehouse_sync.py`): Article bootstrap, inbound detection, inventory reconciliation
- **Project Sync Worker**: Listens to Project requests, queries Odoo, creates Reservations/Shortages
- **Inventory Sync Worker**: Periodically updates stock levels from Odoo to FIWARE
- **NGSI-LD Client**: Manages context entities (UPSERT/PATCH operations)
- **Odoo Client**: JSON-RPC wrapper with retry logic

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.10+ (for local development — matches Vulcanexus Humble)
- Poetry (for dependency management)
- ROS2 Humble / Vulcanexus Humble (optional, for local ROS2 development)

### Option 1: Docker with Full Stack (Recommended)

```bash
cd hermes_main/deployment

# Start core + adapter + mocks
docker compose --profile full --profile mocks up -d

# Verify health
curl http://localhost:8080/healthz

# Check ROS2 services (from inside a ROS2 container)
ros2 service list | grep hermes
```

### Option 2: Docker with Mock Services

```bash
cd hermes_main/deployment

# Start with NullWarehouseClient (no real Hanel needed)
docker compose up -d

# The adapter runs with WAREHOUSE_BACKEND=null by default
curl http://localhost:8080/readyz
```

### Option 3: Local Development

```bash
cd hermes_odoo_adapter

# Install Python dependencies
poetry install

# Copy and customize configuration
cp .env.example .env

# Run locally (ROS2 features require sourcing Vulcanexus setup first)
source /opt/ros/humble/setup.bash
poetry run python -m hermes_odoo_adapter.main
```

## Configuration

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ORION_URL` | Orion-LD endpoint | `http://localhost:1026` |
| `ODOO_URL` | Odoo JSON-RPC endpoint | `http://localhost:8069/jsonrpc` |
| `ODOO_DB` | Odoo database name | `odoo` |
| `ADAPTER_PUBLIC_URL` | Public URL for Orion subscriptions | `http://localhost:8080` |
| `PROJECT_MAPPING_FILE` | SKU-to-project mapping | `project_mapping.json` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Warehouse Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `WAREHOUSE_BACKEND` | Backend type: `hanel_soap` or `null` | `null` |
| `ASRS_SOAP_URL` | Hanel SOAP WSDL URL | `None` |
| `ASRS_SOAP_TIMEOUT` | SOAP request timeout (seconds) | `10` |
| `ASRS_JOB_POLL_INTERVAL` | Job status polling interval (seconds) | `2.0` |
| `WAREHOUSE_SYNC_ENABLED` | Enable warehouse sync worker | `false` |
| `WAREHOUSE_SYNC_INTERVAL_MINUTES` | Sync interval | `5` |

### ROS2 Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ROS2_ENABLED` | Enable ROS2 node | `true` |
| `ROS2_NODE_NAME` | ROS2 node name | `hermes_adapter` |
| `ROS_DOMAIN_ID` | DDS domain ID | `42` |

### Inventory Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `INVENTORY_SYNC_ENABLED` | Enable inventory sync | `true` |
| `INVENTORY_SYNC_INTERVAL_MINUTES` | Sync frequency | `10` |
| `STOCK_LOCATION_ID` | Odoo stock location ID | `8` |
| `INVENTORY_ALLOWED_SKUS` | Comma-separated SKU filter | (all SKUs) |

See [.env.example](./.env.example) for complete configuration options.

## ROS2 Interfaces

### Services

| Service | Type | Description |
|---------|------|-------------|
| `/hermes/warehouse/pick` | `WarehousePick` | Send pick order to warehouse (presents tray) |
| `/hermes/warehouse/status` | `WarehousePickStatus` | Poll pick order status (tray ready?) |
| `/hermes/warehouse/cancel` | `WarehousePickCancel` | Cancel pending pick order |
| `/hermes/stock/consume` | `ConsumeStock` | Decrement stock after cobot pick |
| `/hermes/stock/produce` | `ProduceStock` | Increment finished product stock |
| `/hermes/articles/push` | `PushArticle` | Push article master data to warehouse |

### Topics

| Topic | Type | Direction | Description |
|-------|------|-----------|-------------|
| `/hermes/inventory_updates` | `InventoryUpdate` | Published | Stock change events |
| `/hermes/mission_state` | `MissionState` | Subscribed | Mission state → FIWARE sync |

### Service Usage Examples

```bash
# Send a warehouse pick order
ros2 service call /hermes/warehouse/pick hermes_msgs/srv/WarehousePick \
  "{job_id: '', sku: 'ARTICOLO5', quantity: 10}"

# Check pick status
ros2 service call /hermes/warehouse/status hermes_msgs/srv/WarehousePickStatus \
  "{job_id: 'M123-a1b2c3d4'}"

# Consume stock after picking
ros2 service call /hermes/stock/consume hermes_msgs/srv/ConsumeStock \
  "{project_id: 'P123', sku: 'ARTICOLO5', quantity: 8}"

# Produce finished goods
ros2 service call /hermes/stock/produce hermes_msgs/srv/ProduceStock \
  "{project_id: 'P123', sku: 'CTRL-PANEL-A1', quantity: 1}"
```

## HTTP API Endpoints

### Monitoring & Health
- `GET /healthz` - Liveness probe
- `GET /readyz` - Readiness probe (checks Orion, Odoo, warehouse, ROS2 connectivity)
- `GET /metrics` - Prometheus metrics

### Stock Operations (HTTP)
- `POST /api/consume` - Consume stock for a SKU
- `POST /api/produce` - Produce finished goods

### Webhooks & Notifications
- `POST /orion/notifications` - Orion subscription webhook for Project entities

### Administration
- `POST /admin/recompute/{projectId}` - Force recomputation of reservation/shortage
- `GET /admin/inventory/sync` - Trigger full inventory synchronization
- `GET /admin/inventory/status` - Get inventory sync worker status
- `POST /admin/inventory/sync/{sku}` - Sync specific product inventory

## Warehouse Backends

### HanelSoapClient (Production)

For Hanel vertical warehouses (Lean-Lift / Multi-Space) with MP 12N-S / MP 100D controllers:

```bash
WAREHOUSE_BACKEND=hanel_soap
ASRS_SOAP_URL=http://172.16.1.100/ws/com?wsdl
ASRS_SOAP_TIMEOUT=30
```

SOAP methods used:
- `sendJobsReqV01` — Send pick orders (present tray at window)
- `readAllJobsReqV01` — Poll order status
- `deleteJobReqV01` — Cancel pending orders
- `sendAPDReqV01` — Push article master data
- `readAllAMDReqV01` — Read full inventory snapshot

### NullWarehouseClient (Dev/Test)

Returns mock success responses with no external dependencies. Replaces the previous WireMock ASRS container:

```bash
WAREHOUSE_BACKEND=null  # default
```

## NGSI-LD Entities

### Project
```json
{
  "id": "urn:ngsi-ld:Project:P123",
  "type": "Project",
  "code": {"type": "Property", "value": "CTRL-PANEL-A1"},
  "station": {"type": "Property", "value": "S2"},
  "status": {"type": "Property", "value": "requested"}
}
```

### Reservation
```json
{
  "id": "urn:ngsi-ld:Reservation:P123",
  "type": "Reservation",
  "projectRef": {"type": "Relationship", "object": "urn:ngsi-ld:Project:P123"},
  "lines": {"type": "Property", "value": [
    {"sku": "SCH-REL-24V", "qty": 4},
    {"sku": "ABB-MCB-10A", "qty": 2}
  ]},
  "status": {"type": "Property", "value": "created"}
}
```

### InventoryItem (enriched with warehouse location)
```json
{
  "id": "urn:ngsi-ld:InventoryItem:ARTICOLO5",
  "type": "InventoryItem",
  "sku": {"type": "Property", "value": "ARTICOLO5"},
  "available": {"type": "Property", "value": 42},
  "reserved": {"type": "Property", "value": 10},
  "location": {"type": "Property", "value": "L1-S7"}
}
```

## Docker

### Build

The Dockerfile uses a multi-stage build based on `eprosima/vulcanexus:humble`:

```bash
# Build from repo root (needs access to hermes_msgs)
docker build -f hermes_odoo_adapter/Dockerfile .
```

### Docker Compose

The adapter is defined in `hermes_main/deployment/docker-compose.yml`:

```bash
# Core stack (adapter + Orion-LD + MongoDB)
docker compose up -d

# Full stack with Odoo, monitoring, ROS2
docker compose --profile full --profile ros --profile monitoring up -d
```

### Docker Profiles

| Profile | Services |
|---------|----------|
| (default) | Orion-LD, MongoDB, Adapter |
| `full` | + Odoo, PostgreSQL, Admin Dashboard |
| `ros` | + Mission Controller, AGV Action Server, Metrics Exporter |
| `mocks` | + AGV Mock (WireMock), Perception Stub |
| `monitoring` | + Prometheus, Grafana |

## Development

### Local Setup

```bash
poetry install

# Run tests
pytest tests/

# Lint
ruff check src/
black --check src/
mypy src/
```

### Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires Docker stack)
pytest tests/integration/

# Coverage report
pytest --cov=hermes_odoo_adapter --cov-report=html
```

## Monitoring

### Prometheus Metrics

Available at `/metrics`:

- `http_requests_total` — Request counter
- `odoo_requests_duration_seconds` — Odoo call latencies
- `orion_operations_total` — NGSI-LD operations
- `reservations_created_total` — Successful reservations
- `shortages_created_total` — Stock shortages

### Structured Logging

JSON logs with correlation IDs via `structlog`:

```json
{
  "timestamp": "2025-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "hermes_odoo_adapter.ros2_node",
  "message": "Warehouse pick completed",
  "job_id": "M123-a1b2c3d4",
  "sku": "ARTICOLO5"
}
```

## Related Documentation

- [ASRS SOAP Integration Architecture](../docs/ASRS_SOAP_INTEGRATION_ARCHITECTURE.md) — Full architecture design for Hanel warehouse integration
- [HERMES Main README](../hermes_main/README.md) — System-level overview
- [FIWARE Orion-LD](https://github.com/FIWARE/context.Orion-LD) — NGSI-LD Context Broker
- [Vulcanexus](https://vulcanexus.io/) — eProsima Fast-DDS distribution for ROS2
- [Odoo](https://github.com/odoo/odoo) — Open Source ERP

## License

Apache License 2.0 — see [LICENSE](./LICENSE) file.
