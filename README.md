# HERMES Odoo Adapter

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docs.docker.com/compose/)

A **FIWARE NGSI-LD adapter** that bridges **Odoo ERP systems** with **FIWARE Context Brokers** for smart manufacturing scenarios in the HERMES project.

## ✨ Key Features

✅ **Real-time Project Processing**: Automatically processes manufacturing projects from NGSI-LD notifications  
✅ **BOM Resolution**: Resolves Bills of Materials and checks component availability  
✅ **Stock Management**: Synchronizes inventory between Odoo and NGSI-LD context  
✅ **Reservation & Shortage Handling**: Creates reservations for available materials, shortages for missing ones  
✅ **Production Ready**: Circuit breakers, retry logic, metrics, and comprehensive logging  
✅ **Docker-First**: Optimized for containerized deployment (including M1 Mac support)  
✅ **Comprehensive Testing**: Unit and integration tests with >90% coverage

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose (with ARM64 support for M1 Mac)
- Python 3.11+ (optional, for local development)
- Poetry (optional, for dependency management)

### Option 1: Demo with Mock Services (Fastest)

Perfect for development and testing:

```bash
# Clone the repository
git clone https://github.com/Ampero-SRL/hermes-odoo-adapter.git
cd hermes-odoo-adapter

# Start the demo stack (Orion-LD + Odoo Mock + Adapter)
make up

# Seed with demo data
make seed

# Test the integration
make demo-happy
```

### Option 2: Full Stack with Real Odoo

For production-like testing:

```bash
# Start full stack (takes ~3-5 minutes for Odoo to initialize)
make up-full

# Wait for Odoo to be ready, then seed
make seed-full

# Test with real ERP system
make demo-happy
```

### Option 3: Connect to Existing Orion-LD

If you already have Orion-LD running:

```bash
# Copy and customize configuration
cp .env.example .env
# Edit ORION_URL to point to your existing instance

# Start only the adapter
docker compose up adapter

# Or run locally
poetry install
poetry run python -m hermes_odoo_adapter.main
```

## 📋 Installation Guide

### 1. System Requirements

**For Docker deployment:**
- Docker Desktop 4.0+ (on M1 Mac, ensure Rosetta 2 is enabled)
- 4GB+ available RAM
- 2GB+ available disk space

**For local development:**
- Python 3.11+
- Poetry 1.5+
- Git

### 2. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/Ampero-SRL/hermes-odoo-adapter.git
cd hermes-odoo-adapter

# Install Python dependencies (for local development)
poetry install

# Copy configuration template
cp .env.example .env
```

### 3. Configuration

Edit `.env` to customize your deployment:

```bash
# Core Services
ORION_URL=http://localhost:1026          # Your Orion-LD instance
ODOO_URL=http://localhost:8069/jsonrpc   # Your Odoo instance
ODOO_DB=odoo                             # Odoo database name
ODOO_USER=admin                          # Odoo username
ODOO_PASSWORD=admin                      # Odoo password

# Adapter Configuration
ADAPTER_PUBLIC_URL=http://localhost:8080 # For Orion subscriptions
LOG_LEVEL=INFO                           # Logging level
INVENTORY_SYNC_ENABLED=true              # Enable inventory sync
INVENTORY_SYNC_INTERVAL_MINUTES=10       # Sync frequency

# Optional: Project code mapping
PROJECT_MAPPING_FILE=project_mapping.json
```

### 4. Deployment Options

#### 🚀 **Demo Stack (Recommended for Testing)**
```bash
make up        # Mock services (fastest startup)
make seed      # Populate with demo data
make logs      # Monitor logs
```

#### 🏭 **Production Stack**
```bash
make up-full      # Real Odoo + PostgreSQL
make seed-full    # Seed real systems
make logs-full    # Monitor all services
```

#### 📊 **With Monitoring**
```bash
make up-monitoring  # Add Prometheus + Grafana
# Access Grafana: http://localhost:3000 (admin/admin)
# Access Prometheus: http://localhost:9090
```

## 🔗 Integration with Existing Systems

### Using Existing Orion-LD

If you already have Orion-LD deployed:

1. **Configure the adapter** to connect to your existing instance:
```bash
# In your .env file
ORION_URL=http://your-existing-orion:1026
ORION_TENANT=your-tenant        # Optional
ORION_SERVICE_PATH=/your-path   # Optional
```

2. **Deploy only the adapter:**
```bash
# Option A: Docker with override
cat > docker-compose.override.yml << EOF
version: '3.8'
services:
  adapter:
    environment:
      - ORION_URL=http://your-orion:1026
    networks:
      - your-existing-network

# Comment out or remove mongo and orion-ld services if using existing
# mongo:
#   image: mongo:6
# orion-ld:
#   image: fiware/orion-ld:1.4.0

networks:
  your-existing-network:
    external: true
EOF

docker-compose up adapter

# Option B: Run locally
poetry run python -m hermes_odoo_adapter.main
```

3. **Ensure network connectivity:**
   - Adapter needs HTTP access to Orion-LD (port 1026)
   - Orion-LD needs HTTP access back to adapter for subscriptions
   - Configure `ADAPTER_PUBLIC_URL` to be reachable from Orion-LD

### Using Existing Odoo

For existing Odoo installations:

1. **Verify required modules** are installed:
   - `base` (core)
   - `product` (product management)
   - `mrp` (manufacturing)  
   - `stock` (inventory management)

2. **Configure connection:**
```bash
ODOO_URL=http://your-odoo-server:8069/jsonrpc
ODOO_DB=your-database-name
ODOO_USER=integration-user
ODOO_PASSWORD=secure-password
```

3. **Set up integration user** in Odoo with permissions for:
   - Reading products, BOMs, stock quantities
   - Creating stock adjustments (if using write operations)

### Kubernetes Deployment

For Kubernetes environments:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hermes-odoo-adapter
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hermes-odoo-adapter
  template:
    metadata:
      labels:
        app: hermes-odoo-adapter
    spec:
      containers:
      - name: adapter
        image: hermes-odoo-adapter:latest
        env:
        - name: ORION_URL
          value: "http://orion-ld-service:1026"
        - name: ODOO_URL
          value: "http://odoo-service:8069/jsonrpc"
        ports:
        - containerPort: 8080
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
        readinessProbe:
          httpGet:
            path: /readyz  
            port: 8080
```

## 🎮 Usage Examples

### Basic Manufacturing Flow

1. **Create a Project in Orion-LD:**
```bash
curl -X POST http://localhost:1026/ngsi-ld/v1/entities \
  -H 'Content-Type: application/ld+json' \
  -d '{
    "id": "urn:ngsi-ld:Project:my-project-001",
    "type": "Project",
    "code": {
      "type": "Property",
      "value": "CTRL-PANEL-A1"
    },
    "station": {
      "type": "Property", 
      "value": "STATION-A"
    },
    "status": {
      "type": "Property",
      "value": "planning"
    },
    "@context": "https://fiware.github.io/NGSI-LD_Tutorials/datamodels/ngsi-context.jsonld"
  }'
```

2. **Trigger Processing by Changing Status:**
```bash
curl -X PATCH http://localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:Project:my-project-001/attrs \
  -H 'Content-Type: application/ld+json' \
  -d '{
    "status": {
      "type": "Property",
      "value": "requested"
    }
  }'
```

3. **Check Results:**
```bash
# Check for successful reservation
curl 'http://localhost:1026/ngsi-ld/v1/entities?type=Reservation' | jq

# Or check for shortages
curl 'http://localhost:1026/ngsi-ld/v1/entities?type=Shortage' | jq

# Monitor inventory
curl 'http://localhost:1026/ngsi-ld/v1/entities?type=InventoryItem' | jq
```

### Administrative Operations

```bash
# Manually trigger project recomputation
curl -X POST http://localhost:8080/admin/recompute/my-project-001 \
  -H 'Content-Type: application/json' \
  -d '{"projectCode": "CTRL-PANEL-A1", "station": "STATION-A"}'

# Trigger inventory synchronization
curl -X GET http://localhost:8080/admin/inventory/sync

# Check adapter health
curl http://localhost:8080/healthz
curl http://localhost:8080/readyz

# View metrics
curl http://localhost:8080/metrics
```

## 🏗️ Architecture

The adapter acts as a bridge between FIWARE NGSI-LD context and Odoo ERP:

```
[Orion-LD] ←→ [HERMES Adapter] ←→ [Odoo ERP]
    ↓              ↓                  ↓
Projects    Reservations/         BOM/Stock
Missions    Shortages/            Products
Tasks       InventoryItems        Locations
```

### Key Components

- **Project Sync Worker**: Listens to Project requests, queries Odoo, creates Reservations/Shortages
- **Inventory Sync Worker**: Periodically updates stock levels
- **NGSI-LD Client**: Manages context entities (UPSERT/PATCH operations)
- **Odoo Client**: JSON-RPC wrapper with retry logic

## 📊 NGSI-LD Entities

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

### Shortage
```json
{
  "id": "urn:ngsi-ld:Shortage:P123",
  "type": "Shortage",
  "projectRef": {"type": "Relationship", "object": "urn:ngsi-ld:Project:P123"},
  "lines": {"type": "Property", "value": [
    {"sku": "SCH-REL-24V", "missingQty": 2}
  ]},
  "status": {"type": "Property", "value": "open"}
}
```

## 🔧 Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ORION_URL` | Orion-LD endpoint | `http://localhost:1026` |
| `ODOO_URL` | Odoo JSON-RPC endpoint | `http://localhost:8069/jsonrpc` |
| `ODOO_DB` | Odoo database name | `odoo` |
| `SKU_FIELD` | Product SKU field | `default_code` |
| `POLL_INTERVAL_SECONDS` | Inventory sync interval | `60` |

See [.env.example](./.env.example) for complete configuration options.

## 🛠️ Development

### Local Setup

1. **Install dependencies:**
   ```bash
   poetry install
   ```

2. **Run tests:**
   ```bash
   make test
   ```

3. **Start development server:**
   ```bash
   poetry run python -m hermes_odoo_adapter.main
   ```

### Docker Development

```bash
# Build and start services
make up

# Watch logs
make logs

# Run tests in Docker
docker-compose exec adapter pytest

# Rebuild after changes
make rebuild
```

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires Docker stack)
pytest tests/integration/

# Coverage report
pytest --cov=hermes_odoo_adapter --cov-report=html
```

## 📡 API Endpoints

- `GET /healthz` - Liveness probe
- `GET /readyz` - Readiness probe (checks Orion/Odoo connectivity)
- `GET /metrics` - Prometheus metrics
- `POST /orion/notifications` - Orion subscription webhook
- `POST /admin/recompute/{projectId}` - Force recomputation
- `GET /debug/reservation/{projectId}` - Debug reservation

## 🐳 Docker Profiles

- **Default**: Orion-LD + Odoo Mock + Adapter
- **Full** (`--profile full`): + Real Odoo + PostgreSQL

```bash
# Start with real Odoo
docker-compose --profile full up
```

## 📈 Monitoring

### Metrics

Prometheus metrics available at `/metrics`:

- `http_requests_total` - Request counter
- `odoo_requests_duration_seconds` - Odoo call latencies
- `orion_operations_total` - NGSI-LD operations
- `reservations_created_total` - Successful reservations
- `shortages_created_total` - Stock shortages

### Logging

Structured JSON logs with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "hermes_odoo_adapter.workers.project_sync",
  "message": "Created reservation for project",
  "projectId": "P123",
  "reservationId": "urn:ngsi-ld:Reservation:P123",
  "lines": 3
}
```

## 🔐 Security

- API key authentication (optional)
- FIWARE service/tenant headers support
- No secrets in container images
- Non-root container execution

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

## 📄 License

Apache License 2.0 - see [LICENSE](./LICENSE) file.

## 🆘 Troubleshooting

### Common Issues

**1. Services not starting on M1 Mac**
```bash
# Ensure Docker Desktop has Rosetta 2 enabled
# In Docker Desktop: Settings → General → Use Rosetta for x86/amd64 emulation
```

**2. Odoo initialization taking too long**
```bash
# Monitor Odoo startup logs
make logs-odoo

# Odoo typically takes 3-5 minutes on first startup
# Look for "odoo.modules.loading: Modules loaded." message
```

**3. Connection refused errors**
```bash
# Check all services are healthy
make health

# Verify network connectivity
docker network ls
docker network inspect hermes_network
```

**4. Orion-LD subscription not working**
```bash
# Check Orion-LD subscriptions
curl http://localhost:1026/ngsi-ld/v1/subscriptions

# Check adapter logs for subscription setup
make logs-adapter

# Verify ADAPTER_PUBLIC_URL is accessible from Orion-LD
curl $ADAPTER_PUBLIC_URL/healthz
```

**5. Adapter can't connect to existing Orion-LD**
```bash
# Test connectivity from adapter container
docker exec -it hermes-adapter curl http://your-orion:1026/version

# Check if your Orion-LD accepts connections from adapter's network
# Make sure firewall/security groups allow traffic on port 1026
```

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/Ampero-SRL/hermes-odoo-adapter/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Ampero-SRL/hermes-odoo-adapter/discussions)

## 🔗 Related Projects

- [FIWARE Orion-LD](https://github.com/FIWARE/context.Orion-LD) - NGSI-LD Context Broker
- [Odoo](https://github.com/odoo/odoo) - Open Source ERP
- [HERMES Project](https://github.com/Ampero-SRL) - Smart Manufacturing Initiative