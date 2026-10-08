"""Synthetic approved-source builders for isolated publication tests."""

from pathlib import Path
import hashlib
import json
import subprocess
import yaml


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def repo(root: Path, name: str, text: str) -> tuple[Path, str]:
    r = root / name
    r.mkdir()
    git(r, "init", "-q")
    git(r, "config", "user.email", "t@invalid")
    git(r, "config", "user.name", "T")
    (r / "README.md").write_text(text)
    (r / "LICENSE").write_text("MIT License\n")
    git(r, "add", ".")
    git(r, "commit", "-qm", "content")
    content = git(r, "rev-parse", "HEAD")
    rights = {"spdx_license": "MIT", "license_file": "LICENSE"}
    if name == "dasc":
        rights["attribution"] = "Test"
    contract = {
        "schema_version": 1,
        "project": name,
        "repository": f"https://github.com/pydasc/{name}",
        "source_commit": content,
        "files": [
            {
                "source": "README.md",
                "destination": f"{name}/index.md",
                "media_type": "text/markdown",
                "documentation_status": {"label": "Reviewed", "evidence": "test"},
                "redistribution": rights,
            }
        ],
    }
    if name == "dasc":
        contract["publication_decision"] = {
            "state": "approved",
            "reason": "test",
            "evidence": "test",
        }
    (r / "docs").mkdir()
    (r / "docs/publication-manifest.json").write_text(json.dumps(contract))
    git(r, "add", ".")
    git(r, "commit", "-qm", "contract")
    return r, git(r, "rev-parse", "HEAD")


def fixture(tmp: Path, ptext="# P\n", dtext="# D\n"):
    p, pc = repo(tmp, "pydasc", ptext)
    d, dc = repo(tmp, "dasc", dtext)
    data = {
        "schema_version": 2,
        "sources": {
            n: {
                "repository": f"https://github.com/pydasc/{n}",
                "checkout_commit": c,
                "publication_manifest": "docs/publication-manifest.json",
                "files": [{"source": "README.md", "destination": f"{n}/index.md"}],
            }
            for n, c in (("pydasc", pc), ("dasc", dc))
        },
    }
    m = tmp / "lock.yml"
    m.write_text(yaml.safe_dump(data))
    return m, p, d


def hashes(root: Path):
    return {
        x.relative_to(root): hashlib.sha256(x.read_bytes()).hexdigest()
        for x in root.rglob("*")
        if x.is_file() and ".git" not in x.parts
    }
