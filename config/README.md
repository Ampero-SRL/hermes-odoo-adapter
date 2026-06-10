# Configuration & DDS ↔ NGSI-LD integration path

This folder is reserved for runtime configuration files (Vulcanexus / Fast-DDS
QoS profiles, DDS Enabler configuration, simulator overrides, etc.).

The remainder of this page answers the D4 §3.2.6 requirement on the
**FIWARE DDS-NGSI-LD integration / DDS Enabler configuration**.

## DDS Enabler — status: **N/A**

The HERMES Odoo Adapter **does not** use the FIWARE DDS NGSI-LD mapping tool
(the *DDS Enabler*) as its integration path. The adapter is a hybrid
Vulcanexus/ROS 2 + FastAPI Python process — it talks DDS natively (via
`rclpy` and the Vulcanexus Fast-DDS implementation) and NGSI-LD natively
(via `httpx` against the Orion-LD Context Broker REST API in
[`src/hermes_odoo_adapter/orion_client.py`](../src/hermes_odoo_adapter/orion_client.py)).
The DDS ↔ NGSI-LD mapping is therefore performed **inside the adapter
process**, not delegated to a sidecar enabler.

| Item | Value |
|---|---|
| DDS Enabler used? | No |
| Reason | Bidirectional, application-specific business logic (Odoo BOM resolution, Hänel SOAP orchestration, Mission Controller hand-offs) sits between the DDS surface and the NGSI-LD surface; a one-shot topic→entity mapping is not sufficient. |
| Alternative integration path | In-process bridging in `ros2_node.py` (DDS publisher / subscriber callbacks) ↔ `orion_client.py` (NGSI-LD CRUD against Orion-LD). |
| DDS Enabler configuration file | none |

## DDS ↔ NGSI-LD mapping summary

For a third party that *does* want to plug the FIWARE DDS Enabler in front
of the adapter (e.g. to consume the same topics from a different
NGSI-LD broker), the following table is the canonical mapping the
adapter implements today.

| ROS 2 topic / service / msg | Direction | NGSI-LD entity / property | Notes |
|---|---|---|---|
| topic `/hermes/inventory_updates` (`hermes_msgs/msg/InventoryUpdate`) | **out (DDS pub)** | `InventoryItem.quantity` (NGSI-LD `PATCH`) | Stock-change events emitted from the adapter; the upstream notification source is Odoo / Hänel reconciliation. Schema: [`contracts/schemas/InventoryItem.schema.json`](../contracts/schemas/InventoryItem.schema.json) |
| topic `/hermes/mission_state` (`std_msgs/String` JSON payload) | **in (DDS sub)** | various — patches `Mission.currentState` and the linked `Project.assemblyStatus` | The adapter parses the JSON payload and applies the relevant property patches. Absorbs the role of the old ROS-FIWARE bridge. |
| topic `/hermes/warehouse/tray_state` (`std_msgs/Int16`, latched) | **out (DDS pub)** | `InventoryItem.warehouseState` *(reference / derived)* | Latched current-tray state from the Hänel HOST-COM client; not strictly bridged to NGSI-LD, but a downstream NGSI-LD consumer can subscribe to it. |
| service `/hermes/warehouse/pick` (`hermes_msgs/srv/WarehousePick`) | **in (DDS req)** | `Reservation` (CREATE / PATCH) | Mission Controller request → tray retrieval → adapter updates the Reservation status. |
| service `/hermes/warehouse/status` (`hermes_msgs/srv/WarehousePickStatus`) | **in (DDS req)** | reads `Reservation.status` | Status poll. |
| service `/hermes/warehouse/cancel` (`hermes_msgs/srv/WarehousePickCancel`) | **in (DDS req)** | `Reservation.status` ← `cancelled` | Cancel an in-flight retrieval. |
| service `/hermes/stock/consume` (`hermes_msgs/srv/ConsumeStock`) | **in (DDS req)** | `InventoryItem.quantity` (decrement) + Odoo stock move | Post-pick stock decrement. |
| service `/hermes/stock/produce` (`hermes_msgs/srv/ProduceStock`) | **in (DDS req)** | `InventoryItem.quantity` (increment) + Odoo finished-goods move | Finished-goods stock increment. |

The NGSI-LD context is in [`contracts/context/context.jsonld`](../contracts/context/context.jsonld);
the entity schemas are in [`contracts/schemas/`](../contracts/schemas/).

## Vulcanexus / Fast-DDS configuration

No custom QoS profile is shipped today. The adapter uses the default ROS 2
profile inherited from the Vulcanexus Humble base image (Fast-DDS), with
`ROS_DOMAIN_ID=42` set by the runtime environment file. When a custom
profile becomes necessary (e.g. for cross-network deployments or stricter
reliability/durability needs), it will live here as `fastdds_profile.xml`
or `qos.yaml` and be sourced by the entrypoint script.

## Future work / known gaps

- A FIWARE DDS Enabler configuration could be added as an optional
  side-car path for third parties that want a wire-compatible NGSI-LD
  bridge without running the adapter; this is **not** on the D4
  submission scope.
- Per-topic QoS overrides (latched durability for state topics, reliable
  for service replies) are currently inherited from the ROS 2 defaults
  and should be documented + tuned in a follow-up.
