# `media/`

Visual artefacts that support the ARISE D4 written report.

| File | Contents |
|---|---|
| [`architecture_diagram.md`](architecture_diagram.md) | Mermaid system-context diagram + a pointer to the ASCII fallback in `../docs/01_arise_context.md`. |
| [`sequence_diagram.md`](sequence_diagram.md) | Three Mermaid sequence diagrams (Project → Shortage, top-up → Reservation, Mission Controller → ConsumeStock). |
| [`video_link.md`](video_link.md) | Demonstrator-video reference + acceptance criteria for the recording. |
| [`diagrams/`](diagrams/) | PNG exports of the architecture + sequence diagrams (for embedding in the written report). |
| [`screenshots/`](screenshots/) | Captured execution logs + Odoo / Grafana / Swagger / ROS 2 evidence from a fresh-clone run. |

The Mermaid sources render inline on GitHub and stay editable as the
architecture evolves; `diagrams/` holds rendered PNGs of the same
diagrams for documents that can't render Mermaid (e.g. the `.docx`).
