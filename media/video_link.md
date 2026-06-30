# Demo

A recorded run of the in-repo **mock-only** demo flow. A reader can watch
the full Quick-Start (`docs/03_installation_and_hello_world.md` →
`docs/04_basic_demo_how_to_use.md`) end to end without setting anything up.

![HERMES Odoo Adapter — demo flow](demo.gif)

- **`demo.gif`** — the rendered clip (~14 s). Renders inline on GitHub above.
- **`demo.cast`** — the source [asciinema](https://asciinema.org) recording
  (captured 2026-06-11). Play locally with `asciinema play media/demo.cast`,
  or `asciinema upload media/demo.cast` to publish a shareable asciinema.org URL.

The GIF was produced from the cast with
[`agg`](https://github.com/asciinema/agg):

```bash
agg --speed 2 --idle-time-limit 1 --theme monokai media/demo.cast media/demo.gif
```

## What the clip shows

The demo walks through the Quick-Start flow:

1. A fresh `git clone https://github.com/Ampero-SRL/hermes-odoo-adapter` + `cd hermes-odoo-adapter`.
2. `cp .env.example .env`.
3. `docker compose -f docker/docker-compose.demo.yml up -d` + wait for `/healthz` (`until curl -sf … ; do sleep 1; done`).
4. `curl -s http://localhost:8080/healthz | jq .` → green output.
5. `curl -sS -i -H "Content-Type: application/ld+json" -X POST http://localhost:1026/ngsi-ld/v1/entities -d @examples/payloads/project.json` → `HTTP/1.1 201 Created`.
6. Trigger the recompute: `curl -sX POST http://localhost:8080/admin/recompute/demo-ctrl-1 -H "Content-Type: application/json" -d '{"projectCode":"DEMO-CTRL"}'` → `queued`.
7. `docker compose ... logs adapter --since=10s | grep "Published ROS4HRI Intent"` → the ROS4HRI Intent line.
8. `bash examples/curl/04_list_entities.sh Shortage | jq` → the `Shortage:demo-ctrl-1` entity.

## Recording it

A self-contained script lives at
[`../scripts/demo_walkthrough.sh`](../scripts/demo_walkthrough.sh) that prints
each command and waits between steps so a recorder can capture the eight beats
above at a readable pace. The two simplest recording paths:

```bash
# (a) asciinema cast — text terminal recording, plays back on a web
#     page or in any modern terminal:
sudo apt install -y asciinema
asciinema rec --command "bash scripts/demo_walkthrough.sh" demo.cast

# (b) vhs tape — GIF/MP4 generated headlessly from a tape file:
go install github.com/charmbracelet/vhs@latest
vhs scripts/demo_walkthrough.tape   # produces demo.gif
```

A pre-made `vhs` tape file is shipped at
[`../scripts/demo_walkthrough.tape`](../scripts/demo_walkthrough.tape).

## Screenshot derivatives

Per-stage screenshots are captured into [`screenshots/`](screenshots/) — see
that directory's `README.md` for the shot list.
