#!/usr/bin/env bash
# A timed walkthrough of the in-repo mock-only demo, intended to be
# screen-recorded (asciinema rec / vhs tape) into the optional ~90 s
# open-module demo clip referenced from media/video_link.md.
#
# Assumes:
#   - You're at the repo root (`cd hermes-odoo-adapter`).
#   - `.env` is in place (`cp .env.example .env` if not).
#   - Docker + jq + curl are available on PATH.
#
# Each "scene" prints a short banner so the recorder sees natural
# beats, then runs the command + waits long enough for the output to
# be readable.

set -euo pipefail

pause() { sleep "${1:-2}"; }
banner() {
    echo
    echo "════════════════════════════════════════════════════════════════"
    echo " $1"
    echo "════════════════════════════════════════════════════════════════"
    pause 1
}

# ── Scene 1: bring up the demo stack ───────────────────────────────
banner "1.  bring up the demo stack"
( set -x; docker compose -f docker/docker-compose.demo.yml up -d )
echo
echo "   waiting for /healthz to go green…"
until curl -sf http://localhost:8080/healthz > /dev/null 2>&1; do sleep 1; done
pause 2

# ── Scene 2: healthz ──────────────────────────────────────────────
banner "2.  /healthz — adapter is live"
( set -x; curl -s http://localhost:8080/healthz | jq . )
pause 3

# ── Scene 3: create a Project in Orion-LD ─────────────────────────
banner "3.  create a Project in the FIWARE digital twin"
( set -x;
  curl -sS -i \
      -H "Content-Type: application/ld+json" \
      -X POST "http://localhost:1026/ngsi-ld/v1/entities" \
      -d @examples/payloads/project.json | head -3
)
pause 3

# ── Scene 4: trigger BOM resolution ───────────────────────────────
banner "4.  trigger the BOM-resolution worker"
( set -x;
  curl -sS -X POST http://localhost:8080/admin/recompute/demo-ctrl-1 \
      -H "Content-Type: application/json" \
      -d '{"projectCode":"DEMO-CTRL"}'
)
pause 4

# ── Scene 5: the ROS4HRI Intent (Sprint 0.4) ──────────────────────
banner "5.  ROS4HRI Intent fired on /intents"
( set -x;
  docker compose -f docker/docker-compose.demo.yml logs adapter --since=8s \
      2>&1 | grep "Published ROS4HRI Intent" | head -1
)
pause 4

# ── Scene 6: the Shortage entity ──────────────────────────────────
banner "6.  Shortage entity created in Orion-LD"
( set -x;
  curl -s "http://localhost:1026/ngsi-ld/v1/entities?type=Shortage" \
      | jq '.[0] | {id, status, lines}'
)
pause 5

echo
echo "════════════════════════════════════════════════════════════════"
echo "  Demo complete — Sprint 0.4 Intent + Sprint 1.5 reproducibility"
echo "  validated end-to-end against a clean clone."
echo "════════════════════════════════════════════════════════════════"
