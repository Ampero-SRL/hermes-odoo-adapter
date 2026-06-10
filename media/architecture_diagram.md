# HERMES Odoo Adapter — architecture diagram

The diagram below renders inline on GitHub. The source is Mermaid (text);
edit this file and the rendering updates.

```mermaid
flowchart LR
    subgraph Robotics["Robotics cell (ROS 2 / Vulcanexus)"]
        MC["Mission Controller<br/>(hermes_main)"]
        Cobot["JAKA Pro 16 / cuMotion"]
        AGV["XBOT AGV"]
        Vision["Jetson + Basler 4K<br/>(detection)"]
        MC -- DDS --> Cobot
        MC -- DDS --> AGV
        Vision -- DDS --> MC
    end

    subgraph Adapter["HERMES Odoo Adapter (this repo)"]
        direction TB
        FAPI["FastAPI HTTP face<br/>:8080 — healthz/readyz/metrics<br/>POST /orion/notifications<br/>POST /api/consume, produce<br/>admin/*"]
        RNODE["rclpy node 'hermes_adapter'<br/>5 srv + 3 pub + 1 sub"]
        OdooClient["OdooClient<br/>(JSON-RPC)"]
        OrionClient["OrionClient<br/>(NGSI-LD)"]
        WClient["WarehouseClient ABC<br/>NullWarehouseClient (default in demo)<br/>HanelHostComClient (TCP HOST-COM, production)<br/>HanelSoapClient (HOST-WEB SOAP, legacy)"]
        FAPI --- OrionClient
        FAPI --- OdooClient
        RNODE --- WClient
        RNODE --- OdooClient
        RNODE --- OrionClient
    end

    subgraph Twin["FIWARE digital twin"]
        Orion["Orion-LD<br/>:1026"]
        Mongo["MongoDB"]
        Orion --- Mongo
    end

    subgraph Plant["Plant / business systems"]
        Odoo["Odoo 17 ERP<br/>JSON-RPC"]
        Hanel["Hänel MP 12N<br/>HOST-COM (TCP 2200)<br/>HOST-WEB SOAP /ws/com?wsdl"]
    end

    subgraph Operator["Operator UI"]
        Hololens["HoloLens AR app<br/>(panelserver + StereoKit)"]
    end

    MC -- DDS services<br/>warehouse/pick · stock/consume --> RNODE
    MC -- DDS topic<br/>/hermes/mission_state --> RNODE
    RNODE -- DDS topic<br/>/hermes/inventory_updates<br/>/hermes/warehouse/tray_state --> MC
    OdooClient -- JSON-RPC --> Odoo
    OrionClient -- NGSI-LD --> Orion
    WClient -- "HOST-COM / SOAP" --> Hanel
    Hololens -- NGSI-LD --> Orion
    Orion -- "subscription notify" --> FAPI
```

## Reading the diagram

- **The adapter is the only hop between business systems (Odoo + Hänel)
  and the robotics / digital-twin world.** Everything else either talks
  ROS 2 (Mission Controller, cobot, AGV, vision) or NGSI-LD (HoloLens AR
  app via the operator panel) — only the adapter speaks both, plus
  Odoo JSON-RPC and Hänel HOST-COM / SOAP.
- The Mission Controller calls ROS 2 services on the adapter
  (`/hermes/warehouse/pick`, `/hermes/stock/consume`, …) and publishes
  `mission_state` for the adapter to mirror into Orion-LD.
- Orion-LD posts subscription notifications back into the FastAPI face
  whenever a new `Project` is created.

A static ASCII version of the same diagram lives at the top of
[`../docs/01_arise_context.md`](../docs/01_arise_context.md) for tools
that don't render Mermaid.

A simpler component-list diagram and the full topic / entity / service
inventory are in [`../docs/02_interfaces.md`](../docs/02_interfaces.md).
