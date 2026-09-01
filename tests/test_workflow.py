from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github/workflows/docs-check.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"
UPDATE_WORKFLOW = ROOT / ".github/workflows/update-source-locks.yml"
ACTION_PIN = re.compile(r"^\s*uses:\s*[^\s@]+@[0-9a-f]{40}\s+#\s+v\d", re.MULTILINE)


def test_docs_check_workflow_is_valid_and_least_privileged() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.load(text, Loader=yaml.BaseLoader)

    assert set(workflow) >= {"name", "on", "permissions", "jobs"}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"docs"}
    assert "pull_request" in workflow["on"]
    assert "push" in workflow["on"]
    assert "workflow_dispatch" not in workflow["on"]
    assert "deploy" not in text.casefold()


def test_docs_check_pins_actions_and_reproduces_local_build() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    uses_lines = [line for line in text.splitlines() if line.strip().startswith("uses:")]

    assert uses_lines
    assert all(ACTION_PIN.match(line) for line in uses_lines)
    for command in (
        "persist-credentials: false",
        "actions/create-github-app-token@",
        "secrets.DASC_DOCS_APP_ID",
        "secrets.DASC_DOCS_APP_PRIVATE_KEY",
        "steps.source-token.outputs.token",
        "http.https://github.com/.extraheader=AUTHORIZATION: basic $auth_header",
        "load_manifest(Path(\"docs-manifest.yml\"))",
        "credential.helper=",
        "core.hooksPath=/dev/null",
        'fetch --quiet --no-tags --depth=1 origin "$content_commit"',
        "python -m pytest",
        "scripts/collect_docs.py",
        "scripts/validate_docs.py",
        "diff --recursive --no-dereference",
        "mkdocs build --strict",
        "scripts/validate_accessibility.py",
        "scripts/validate_physics_docs.py",
    ):
        assert command in text


def test_pages_workflow_has_exact_permissions_and_release_controls() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.load(text, Loader=yaml.BaseLoader)

    assert workflow["permissions"] == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }
    assert workflow["concurrency"] == {
        "group": "pages",
        "cancel-in-progress": "false",
    }
    assert set(workflow["on"]) == {"push", "workflow_dispatch"}
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert set(workflow["jobs"]) == {"build", "deploy"}
    assert workflow["jobs"]["deploy"]["needs"] == "build"
    assert workflow["jobs"]["deploy"]["environment"]["name"] == "github-pages"


def test_pages_artifact_is_validated_scanned_and_sha_pinned() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    uses_lines = [line for line in text.splitlines() if line.strip().startswith("uses:")]

    assert uses_lines and all(ACTION_PIN.match(line) for line in uses_lines)
    required_in_order = (
        "python -m pytest",
        "scripts/collect_docs.py",
        "scripts/validate_docs.py",
        "diff --recursive --no-dereference",
        "mkdocs build --strict",
        "Scan complete site artifact",
        "actions/configure-pages@",
        "actions/upload-pages-artifact@",
    )
    positions = [text.index(item) for item in required_in_order]
    assert positions == sorted(positions)
    assert "persist-credentials: false" in text
    assert "actions/create-github-app-token@" in text
    assert "secrets.DASC_DOCS_APP_ID" in text
    assert "secrets.DASC_DOCS_APP_PRIVATE_KEY" in text
    assert "steps.source-token.outputs.token" in text
    assert "http.https://github.com/.extraheader=AUTHORIZATION: basic $auth_header" in text
    assert 'fetch --quiet --no-tags --depth=1 origin "$content_commit"' in text
    assert "scripts/validate_accessibility.py" in text
    assert "scripts/validate_physics_docs.py" in text
    assert "enablement: false" in text
    assert re.search(r"actions/upload-pages-artifact@[0-9a-f]{40}[^\n]*\n\s+with:\n\s+path: site(?:\n|$)", text)
    assert "gh-pages" not in text
    assert "personal access token" not in text.casefold()

    mkdocs = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
    assert "operations/" in mkdocs["exclude_docs"].splitlines()


def test_source_update_workflow_proposes_validated_review_only_prs() -> None:
    text = UPDATE_WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    uses_lines = [line for line in text.splitlines() if line.strip().startswith("uses:")]

    assert set(workflow["on"]) == {"schedule", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "write", "pull-requests": "write"}
    assert uses_lines and all(ACTION_PIN.match(line) for line in uses_lines)
    assert "scripts/update_source_locks.py" in text
    assert "--skip-unapproved" in text
    assert "credential.helper= clone" in text
    assert 'fetch --quiet --no-tags --depth=1 origin "$content_commit"' in text
    assert "python -m pytest" in text
    assert "mkdocs build --strict" in text
    assert "scripts/validate_accessibility.py" in text
    assert "scripts/validate_physics_docs.py" in text
    assert "gh pr create" in text
    assert "git push" in text
    assert "merge" not in text.casefold().replace("merging", "")
