# Security policy

## Reporting a vulnerability

Please report security vulnerabilities by emailing **tech@ampero.it**
with the subject line `SECURITY — hermes-odoo-adapter`. Include:

- A short description of the issue and its impact.
- Steps to reproduce (a minimal proof of concept is enough).
- Affected commit / tag / Docker image digest.
- Any suggested mitigations.

**Do not open a public GitHub issue** for security problems.

We aim to acknowledge the report within **3 business days** and to
publish a patched release within **30 days** of confirmation. A
public advisory is coordinated with the reporter.

## Supported versions

| Version | Supported |
|---|---|
| `main` branch | ✅ (latest fixes land here first) |
| `v0.4.x` tags | ✅ (security-only patches; intended to remain stable and maintained long-term) |
| Anything before `v0.4.0` | ❌ (pre-release; please move forward) |

## Scope

The adapter is the integration boundary between Odoo, FIWARE
Orion-LD, the Hänel ASRS and a ROS 2 Mission Controller. We accept
security reports for:

- The Python source in `src/hermes_odoo_adapter/`.
- The `docker/` Compose stacks and `Dockerfile` (image hardening,
  privilege escalation, accidental secret exposure).
- The NGSI-LD entity schemas in `contracts/schemas/` (data-validation
  bypass, JSON-LD context attacks).
- The ROS 2 service / topic surface in `ros2_node.py` + the vendored
  `hermes_msgs` package (auth bypass, malformed payloads, DoS).

Out of scope (but please report anyway if it's serious):

- The upstream Vulcanexus / Fast-DDS / Orion-LD / Odoo / Mongo
  images — coordinate with the original vendors. We will help relay
  if needed.
- The `docker/odoo-mock/` mock service — it's deliberately
  permissive for demo purposes; please **don't** point it at the
  internet.

## Defaults & assumptions

The shipped configuration is meant for **single-host development /
demo**:

- No authentication on `:8080`, `:1026`, `:3000`, `:9090`.
- `admin/admin` Grafana credentials (skip-password-change accepted).
- `NullWarehouseClient` accepts every pick request.

Production deployments are expected to put the adapter behind a
reverse proxy that enforces TLS + auth, and to replace the demo
defaults with secrets pulled from your normal secret store. See
[`docs/05_role_in_demonstrator.md`](docs/05_role_in_demonstrator.md)
for the production deployment posture.
