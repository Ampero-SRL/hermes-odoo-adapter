# HERMES TRL6-7 demonstrator video

## Status

[**TBD**] — the canonical demonstrator video URL goes here before the D4
submission tag is cut. See [`../docs/D4_PLAN.md`](../docs/D4_PLAN.md)
for the tracking entry.

## What the video should show (acceptance criteria for the recording)

A reviewer should be able to map each step to a section of the docs:

1. Operator interaction on the HoloLens AR app: project selection
   (maps to the `Project` NGSI-LD entity creation in
   [`../docs/04_basic_demo_how_to_use.md`](../docs/04_basic_demo_how_to_use.md)
   Stage 1).
2. Odoo dashboard with the manufacturing order behind the project
   (proves the BOM-resolution path).
3. Orion-LD entity browser showing the `Reservation` / `Shortage` /
   `InventoryItem` updates in real time (proves the FIWARE digital-twin
   sync).
4. The Hänel vertical lift presenting a tray; the JAKA cobot picking
   the component (the ROS 2 `WarehousePick` + `WarehousePickStatus`
   service round-trip — Stage 2 of `04_basic_demo_how_to_use.md`).
5. AGV transfer + assembly handover (out of scope for the open module
   but relevant for the demonstrator).
6. Operator AR guidance for the manual wiring step and the final
   `Project.status` transition to `completed`.

Total runtime: 3–5 minutes is plenty for D4.

## Hosting

- YouTube (unlisted) is acceptable; embed the link here once recorded.
- For long-term stability (the D4 submission tag must remain stable
  until **2033-06-30**, six years after ARISE ends), prefer a Zenodo /
  institutional repository deposit as the canonical archival URL, with
  the YouTube link as the day-to-day accessible mirror.

## Screenshot derivatives

While the video is being prepared, capture per-stage screenshots into
[`screenshots/`](screenshots/) — see that directory's README for the
shot list.
