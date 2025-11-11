#!/usr/bin/env python3
"""Normalize .env values for docker stack."""
import sys
from pathlib import Path


def normalize_stock_locations(env_path: Path, desired_value: str) -> bool:
    target_key = "STOCK_LOCATION_NAMES="
    lines = env_path.read_text().splitlines()
    changed = False

    for idx, line in enumerate(lines):
        if line.strip().startswith(target_key):
            current_value = line.split("=", 1)[1].strip()
            if current_value != desired_value:
                lines[idx] = f"{target_key}{desired_value}"
                changed = True
            break
    else:
        lines.append(f"{target_key}{desired_value}")
        changed = True

    if changed:
        env_path.write_text("\n".join(lines) + "\n")
    return changed


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("Usage: normalize_env.py <env_path> <desired_value>")

    env_path = Path(sys.argv[1])
    desired_value = sys.argv[2]

    if not env_path.exists():
        sys.exit(f"Env file {env_path} not found")

    changed = normalize_stock_locations(env_path, desired_value)
    if changed:
        print(f"Updated STOCK_LOCATION_NAMES in {env_path}")
    else:
        print("STOCK_LOCATION_NAMES already normalized")


if __name__ == "__main__":
    main()
