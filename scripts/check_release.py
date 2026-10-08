#!/usr/bin/env python3
"""Run the complete local publication checks; never acquire sources or deploy."""

from __future__ import annotations
import argparse
import hashlib
import os
import stat
from types import SimpleNamespace
from pathlib import Path
import subprocess
import sys
import yaml
from safe_files import read_regular_file, filesystem_inside
from publication_errors import CollectionError

ROOT = Path(__file__).resolve().parents[1]


class ReleaseCheckError(CollectionError):
    pass


def _tree_entries(root: Path):
    """Walk regular files/directories without following symlinks or hiding errors."""
    if root.is_symlink() or not root.is_dir():
        raise CollectionError(f"missing/unsafe release directory: {root}")
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as children:
            for child in children:
                path = Path(child.path)
                mode = child.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    yield path, True
                    pending.append(path)
                elif stat.S_ISREG(mode):
                    yield path, False
                else:
                    raise CollectionError(f"unsafe release entry: {path}")


def snapshot(docs: Path) -> dict[str, str | None]:
    """Fingerprint the complete generated tree, including empty directories."""
    inventory = docs / "generated-inventory.json"
    snapshot: dict[str, str | None] = {
        inventory.name: hashlib.sha256(read_regular_file(inventory, "inventory")).hexdigest()
    }
    for namespace in ("pydasc", "dasc"):
        for path, is_directory in _tree_entries(docs / namespace):
            snapshot[path.relative_to(docs).as_posix()] = (
                None
                if is_directory
                else hashlib.sha256(read_regular_file(path, "generated document")).hexdigest()
            )
    return snapshot


def check(options, runner=None) -> list[str]:
    runner = runner or subprocess.run
    config = options.config.resolve(strict=True)
    docs = options.docs.resolve()
    if options.site.is_symlink():
        raise ReleaseCheckError("unsafe site output directory: symlink")
    site = options.site.resolve()
    for source in (options.pydasc.resolve(), options.dasc.resolve()):
        if filesystem_inside(site, source) or filesystem_inside(source, site):
            raise ReleaseCheckError("site output overlaps a source checkout")
    if (
        filesystem_inside(docs, site)
        or filesystem_inside(site, docs)
        or filesystem_inside(config, site)
        or filesystem_inside(options.manifest.resolve(), site)
    ):
        raise ReleaseCheckError("site output overlaps publication inputs")
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


def check_release(root: Path, pydasc: Path, dasc: Path, *, runner=None):
    """Preserve the remote root-based Python API using the shared release pipeline."""
    root = root.resolve()
    return check(
        SimpleNamespace(
            config=root / "mkdocs.yml",
            manifest=root / "docs-manifest.yml",
            docs=root / "docs",
            site=root / "site",
            pydasc=pydasc,
            dasc=dasc,
            skip_tests=True,
            browser_tests=False,
        ),
        runner=runner,
    )


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
