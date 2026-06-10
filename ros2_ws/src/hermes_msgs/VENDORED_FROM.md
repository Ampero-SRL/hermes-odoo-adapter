# Vendored `hermes_msgs`

This `hermes_msgs` package is **vendored** into the adapter so the repo
builds from a clean `git clone` without the rest of the HERMES monorepo.

## Upstream

- Source: `hermes_main/ros2_ws/src/hermes_msgs` in the private HERMES
  integration repo (`Ampero-SRL/hermes_main`).
- Pinned to commit: `9987978de0c25cf8c1106b2db96b20a573edf9cf` (snapshot
  taken 2026-05-27 for D4 submission).

## What the adapter actually uses

| Type | Name | Used in |
|---|---|---|
| `srv` | `WarehousePick` | `/hermes/warehouse/pick` |
| `srv` | `WarehousePickStatus` | `/hermes/warehouse/status` |
| `srv` | `WarehousePickCancel` | `/hermes/warehouse/cancel` |
| `srv` | `ConsumeStock` | `/hermes/stock/consume` |
| `srv` | `ProduceStock` | `/hermes/stock/produce` |
| `msg` | `InventoryUpdate` | `/hermes/inventory_updates` |

The other definitions in this package (vision / cobot pick-place / AGV
actions / gestures) are unused by the adapter but kept in the vendored
snapshot for build parity with the upstream package.

## Maintenance

This snapshot is frozen for the D4 submission and must remain stable
until 2033-06-30 (six years after ARISE ends, per the D4 §3.2.1
stability requirement).

If the upstream interface evolves, refresh by:

```
cp -r <hermes_main>/ros2_ws/src/hermes_msgs/{action,msg,srv,package.xml,CMakeLists.txt} \
      hermes_odoo_adapter/ros2_ws/src/hermes_msgs/
```

and update the pinned commit hash above.
