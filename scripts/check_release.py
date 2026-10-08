#!/usr/bin/env python3
"""Run the complete local publication checks; never acquire sources or deploy."""

from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import yaml
from safe_files import read_regular_file

ROOT = Path(__file__).resolve().parents[1]


class ReleaseCheckError(ValueError):
    pass


def snapshot(docs: Path) -> dict[str, str]:
    paths = [docs / "generated-inventory.json"]
    for name in ("pydasc", "dasc"):
        paths.extend(sorted(p for p in (docs / name).rglob("*") if p.is_file()))
    return {
        str(path.relative_to(docs)): hashlib.sha256(
            read_regular_file(path, "generated snapshot")
        ).hexdigest()
        for path in paths
    }


def check(options, runner=None) -> list[str]:
    runner = runner or subprocess.run
    config = options.config.resolve(strict=True)
    docs = options.docs.resolve()
    site = options.site.resolve()
    settings = yaml.safe_load(config.read_text())
    configured_docs = settings.get("docs_dir", "docs")
    if not isinstance(configured_docs, str) or (config.parent / configured_docs).resolve() != docs:
        raise ReleaseCheckError("--docs must match docs_dir in the supplied MkDocs configuration")
    stages = []

    def execute(stage, args):
        print(f"[{stage}]", flush=True)
        try:
            runner([sys.executable, *args], cwd=config.parent, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ReleaseCheckError(f"release stage failed: {stage}") from exc
        stages.append(stage)

    def script(name, *args):
        return [str(ROOT / "scripts" / name), *map(str, args)]

    collect = script(
        "collect_docs.py",
        "--manifest",
        options.manifest.resolve(),
        "--output",
        docs,
        "--pydasc",
        options.pydasc.resolve(),
        "--dasc",
        options.dasc.resolve(),
    )
    if not options.skip_tests:
        execute("tests", ["-m", "pytest"])
    execute("collect", collect)
    execute(
        "validate-docs",
        script("validate_docs.py", "--manifest", options.manifest.resolve(), "--docs", docs),
    )
    execute("validate-physics", script("validate_physics_docs.py", "--docs", docs))
    before = snapshot(docs)
    execute("collect-repeat", collect)
    if snapshot(docs) != before:
        raise ReleaseCheckError("repeated collection differs from the first generation")
    execute(
        "strict-build",
        [
            "-m",
            "mkdocs",
            "build",
            "--strict",
            "--config-file",
            str(config),
            "--site-dir",
            str(site),
        ],
    )
    execute(
        "validate-site",
        script("validate_site.py", "--site", site, "--css", docs / "stylesheets/readthedocs.css"),
    )
    execute("validate-accessibility", script("validate_accessibility.py", "--site", site))
    execute("scan-artifact", script("validate_artifact.py", "--site", site))
    if getattr(options, "browser_tests", False):
        print("[browser-tests]", flush=True)
        try:
            runner(
                ["node", str(ROOT / "tests/browser/check_navigation.cjs"), str(site)],
                cwd=config.parent,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ReleaseCheckError("release stage failed: browser-tests") from exc
        stages.append("browser-tests")
    return stages


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs-manifest.yml"))
    parser.add_argument("--config", type=Path, default=Path("mkdocs.yml"))
    parser.add_argument("--docs", type=Path, default=Path("docs"))
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--pydasc", type=Path, required=True)
    parser.add_argument("--dasc", type=Path, required=True)
    parser.add_argument(
        "--skip-tests", action="store_true", help="reuse a preceding test run of this same checkout"
    )
    parser.add_argument(
        "--browser-tests",
        action="store_true",
        help="require installed pinned Playwright and Chromium",
    )
    args = parser.parse_args(argv)
    try:
        stages = check(args)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Release checks passed ({len(stages)} stages); no deployment performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
