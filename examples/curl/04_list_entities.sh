#!/usr/bin/env bash
# List all NGSI-LD entities of a given type in Orion-LD.
# Defaults to Project; pass another type as the first argument.
#
# Examples:
#   bash 04_list_entities.sh                # -> all Projects
#   bash 04_list_entities.sh Reservation
#   bash 04_list_entities.sh InventoryItem
#
# Expected output: a JSON array of entities. Empty array means none have
# been created yet (run 03_orion_create_project.sh first).

set -euo pipefail
: "${ORION_URL:=http://localhost:1026}"
ENTITY_TYPE="${1:-Project}"

curl -sS \
    -H "Accept: application/ld+json" \
    "${ORION_URL}/ngsi-ld/v1/entities?type=${ENTITY_TYPE}" \
    | (command -v jq > /dev/null && jq . || cat)
