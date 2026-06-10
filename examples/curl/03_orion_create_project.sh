#!/usr/bin/env bash
# Create a Project NGSI-LD entity in Orion-LD using the sample payload.
# This triggers a subscription notification to the adapter, which then
# resolves the BOM via the Odoo mock and creates Reservation / Shortage
# entities.
#
# Expected output:
#   HTTP/1.1 201 Created
#   Location: .../ngsi-ld/v1/entities/urn:ngsi-ld:Project:demo-ctrl-1
#   (the exact Location header is implementation-dependent; what matters
#    is the 201 status and that the entity is retrievable by id)

set -euo pipefail
: "${ORION_URL:=http://localhost:1026}"
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

curl -sS -i \
    -H "Content-Type: application/ld+json" \
    -X POST "${ORION_URL}/ngsi-ld/v1/entities" \
    -d "@${HERE}/../payloads/project.json"
