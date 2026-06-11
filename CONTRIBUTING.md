# Contributing to the HERMES Odoo Adapter

Thanks for thinking about contributing. This project is an
**ARISE Reusable HRI Module** (D4 / Stage 4 deliverable); the
expectation is that it stays stable until **2033-06-30** (six years
after ARISE ends), so the bar for changes that land on `main` is
intentionally higher than a typical research repo.

## Quick checklist

- [ ] An issue exists for the change (or the change is small + obvious).
- [ ] A fresh clone still passes the Hello World in
      [`docs/03_installation_and_hello_world.md`](docs/03_installation_and_hello_world.md).
- [ ] The Basic Demo in
      [`docs/04_basic_demo_how_to_use.md`](docs/04_basic_demo_how_to_use.md)
      still runs end-to-end against the in-tree `docker/odoo-mock/`.
- [ ] `pytest tests/unit` passes locally.
- [ ] New / changed ROS 2 topics + services are documented in
      [`docs/02_interfaces.md`](docs/02_interfaces.md).
- [ ] New / changed NGSI-LD entity properties are reflected in
      [`contracts/schemas/`](contracts/schemas/) and have a sample
      under [`examples/payloads/`](examples/payloads/).
- [ ] No personally-identifying data, secrets, or customer-specific
      BOMs are committed.

## How to propose a change

1. **Open an issue** at
   <https://github.com/Ampero-SRL/hermes-odoo-adapter/issues>
   describing the problem before writing the patch (skip for typo
   fixes / a few-line README updates).
2. **Fork + branch** from `main`. Branch naming:
   `feat/<short-slug>`, `fix/<short-slug>`, `docs/<short-slug>`.
3. **Open a pull request** against `main`. Link the issue in the PR
   body.
4. **At least one maintainer review** is required before merge. We
   prefer squash-merge with a Conventional-Commits-style title
   (e.g. `fix(orion_client): handle 201 No Content on subscribe`).

## Development environment

```bash
# Install
poetry install
cp .env.example .env

# Lint + format
poetry run ruff check src/ tests/
poetry run black --check src/ tests/

# Unit tests (no Docker needed)
poetry run pytest tests/unit -q

# Integration tests (need Docker)
docker compose -f docker/docker-compose.demo.yml up -d
poetry run pytest tests/integration -q
docker compose -f docker/docker-compose.demo.yml down -v
```

For Vulcanexus / ROS 2 work, see
[`launch/README.md`](launch/README.md) for the path-based and
package-name `ros2 launch` invocations.

## Coding style

- **Python:** PEP 8 + 100-char lines (matches `pyproject.toml`
  `[tool.black]` / `[tool.ruff]`). Type hints required on new public
  functions; `from __future__ import annotations` at the top of new
  modules.
- **Docstrings:** Google style; the *why* matters more than the
  *what*.
- **Tests:** `pytest`. Async code uses `pytest-asyncio`. Mock the
  Odoo / Orion / Hänel boundaries; don't hit the network in unit
  tests.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`,
  `refactor:`, `test:`, `chore:`). One logical change per commit.

## What's out of scope

The adapter is the **integration backbone** — it does not include the
cobot motion logic, the vision detection, the AGV driver, or the
HoloLens AR app. Those live in separate HERMES repositories
(`hermes_main/`, `hermes_asrs_station/`, `ARISE-AR-APP/`). PRs trying
to expand the adapter into any of those areas will be redirected.

## Reporting security issues

See [`SECURITY.md`](SECURITY.md). Please **do not** open a public
issue for security problems.

## Code of conduct

Participation is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md).
