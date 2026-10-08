#!/usr/bin/env python3
"""Verify reviewed dependency pins using distribution metadata, without importing packages."""

from importlib import metadata
from pathlib import Path
import platform
import sys
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def read_pins(path: Path) -> dict[str, str]:
    pins = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        req = Requirement(line)
        specs = list(req.specifier)
        if (
            req.url
            or req.marker
            or req.extras
            or len(specs) != 1
            or specs[0].operator != "=="
            or "*" in specs[0].version
        ):
            raise ValueError(f"{path.name}: every dependency must have one exact version")
        name = canonicalize_name(req.name)
        if name in pins:
            raise ValueError(f"{path.name}: duplicate dependency {name}")
        pins[name] = specs[0].version
    return pins


def validate(root: Path = ROOT):
    expected_python = (root / ".python-version").read_text().strip()
    if platform.python_version() != expected_python:
        raise ValueError(
            f"Python {expected_python} is required for the reviewed release environment"
        )
    pins = read_pins(root / "requirements-docs.txt")
    direct = read_pins(root / "requirements-docs.in")
    for name, version in direct.items():
        if pins.get(name) != version:
            raise ValueError(f"direct intent and install lock disagree for {name}")
    for name, version in pins.items():
        dist = metadata.distribution(name)
        if dist.version != version:
            raise ValueError(f"installed {name} does not match its reviewed pin {version}")
        requires_python = dist.metadata.get("Requires-Python")
        if requires_python and platform.python_version() not in SpecifierSet(requires_python):
            raise ValueError(f"Python does not satisfy {name} metadata")
        for raw in dist.requires or []:
            req = Requirement(raw)
            if req.marker and not req.marker.evaluate({"extra": ""}):
                continue
            dependency = canonicalize_name(req.name)
            if req.url or dependency not in pins or pins[dependency] not in req.specifier:
                raise ValueError(
                    f"lock is missing a compatible active dependency: {name} -> {dependency}"
                )
    return len(pins)


def main():
    try:
        count = validate()
    except (ValueError, OSError, metadata.PackageNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Verified {count} exact documentation pins and Python {platform.python_version()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
