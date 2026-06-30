# `media/`

Visual artefacts: diagrams, the recorded demo, and captured evidence.

| File | Contents |
|---|---|
| [`diagrams/system_overview.png`](diagrams/system_overview.png) | One-page high-level system architecture: ROS 2 nodes, key topics, middleware layers, operator flow, and module boundaries (this adapter highlighted). |
| [`architecture_diagram.md`](architecture_diagram.md) | Mermaid system-context diagram + a pointer to the ASCII fallback in `../docs/01_arise_context.md`. |
| [`sequence_diagram.md`](sequence_diagram.md) | Three Mermaid sequence diagrams (Project → Shortage, top-up → Reservation, Mission Controller → ConsumeStock). |
| [`video_link.md`](video_link.md) | Notes on the recorded demo (`demo.gif`) and how to reproduce it. |
| [`demo.gif`](demo.gif) | Rendered clip of the mock-only Quick-Start flow, recorded from `demo.cast`. |
| [`demo.cast`](demo.cast) | The asciinema source recording of the demo flow. |
| [`diagrams/`](diagrams/) | PNG exports of the architecture + sequence diagrams (for documents that can't render Mermaid). |
| [`screenshots/`](screenshots/) | Captured execution logs + Odoo / Grafana / Swagger / ROS 2 evidence from a fresh-clone run. |

The Mermaid sources render inline on GitHub and stay editable as the
architecture evolves; `diagrams/` holds rendered PNGs of the same
diagrams for documents that can't render Mermaid (e.g. a `.docx`).
