"""Workflow trust boundaries and release order, independent of YAML formatting."""

from pathlib import Path
import re
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github/workflows/docs-check.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"
UPDATE_WORKFLOW = ROOT / ".github/workflows/update-source-locks.yml"


def load(path):
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


def commands(job):
    return [step.get("run", "") for step in job["steps"]]


def step_index(job, needle):
    matches = [
        i
        for i, step in enumerate(job["steps"])
        if needle in step.get("run", "") or needle in step.get("uses", "")
    ]
    assert matches, f"missing required stage: {needle}"
    return matches[0]


def assert_order(job, stages):
    positions = [step_index(job, name) for name in stages]
    assert positions == sorted(positions)


def test_actions_are_immutable_and_source_credentials_are_protected():
    consumers = set()
    for path in (WORKFLOW, DEPLOY_WORKFLOW, UPDATE_WORKFLOW):
        workflow = load(path)
        for name, job in workflow["jobs"].items():
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", step["uses"])
            if "DASC_DOCS_APP_" not in yaml.safe_dump(job):
                continue
            consumers.add((path.name, name))
            assert job["environment"] == "docs-sources"
            expected = {
                "docs-check.yml": "github.event_name == 'push' && github.ref == 'refs/heads/main'",
                "deploy-pages.yml": "github.ref == 'refs/heads/main' && (github.event_name == 'push' || github.event_name == 'workflow_dispatch')",
                "update-source-locks.yml": "github.ref == 'refs/heads/main' && (github.event_name == 'schedule' || github.event_name == 'workflow_dispatch')",
            }
            assert job["if"] == expected[path.name]
            tokens = [
                step
                for step in job["steps"]
                if step.get("uses", "").startswith("actions/create-github-app-token@")
            ]
            assert len(tokens) == 1
            settings = tokens[0]["with"]
            assert settings["permission-contents"] == "read"
            assert settings["owner"] == "pydasc"
            assert settings["repositories"].split() == ["pydasc", "dasc"]
            assert set(k for k in settings if k.startswith("permission-")) == {
                "permission-contents"
            }
    assert consumers == {
        ("docs-check.yml", "source-docs"),
        ("deploy-pages.yml", "build"),
        ("update-source-locks.yml", "propose"),
    }


def test_untrusted_pr_job_is_source_free_and_read_only():
    workflow = load(WORKFLOW)
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"docs", "source-docs"}
    job = workflow["jobs"]["docs"]
    assert "environment" not in job
    assert "secrets." not in yaml.safe_dump(job)
    assert "source-token" not in yaml.safe_dump(job)
    assert any("load_manifest" in command for command in commands(job))
    assert any("python -m pytest" in command for command in commands(job))
    assert workflow["jobs"]["source-docs"]["needs"] == "docs"
    assert set(workflow["on"]) == {"push", "pull_request"}
    for event in ("push", "pull_request"):
        assert ".github/workflows/deploy-pages.yml" in workflow["on"][event]["paths"]
        assert "pyproject.toml" in workflow["on"][event]["paths"]
    assert "actions/deploy-pages@" not in WORKFLOW.read_text()


def test_release_jobs_check_outputs_before_upload_or_proposal():
    for path, name in [
        (WORKFLOW, "source-docs"),
        (DEPLOY_WORKFLOW, "build"),
        (UPDATE_WORKFLOW, "propose"),
    ]:
        job = load(path)["jobs"][name]
        checks = [
            step for step in job["steps"] if "scripts/check_release.py" in step.get("run", "")
        ]
        assert len(checks) == 1
        assert "--pydasc .source-checkouts/pydasc" in checks[0]["run"]
        assert "--dasc .source-checkouts/dasc" in checks[0]["run"]
        assert ("--skip-tests" in checks[0]["run"]) is (path == WORKFLOW)
        if path == DEPLOY_WORKFLOW:
            assert_order(
                job,
                [
                    "scripts/check_release.py",
                    "actions/configure-pages@",
                    "actions/upload-pages-artifact@",
                ],
            )
        elif path == UPDATE_WORKFLOW:
            assert_order(
                job, ["scripts/update_source_locks.py", "scripts/check_release.py", "gh pr create"]
            )
            assert checks[0]["if"] == "steps.changes.outputs.changed == 'true'"


def test_private_acquisition_has_explicit_modes_and_no_persisted_website_credentials():
    for path, name in [
        (WORKFLOW, "source-docs"),
        (DEPLOY_WORKFLOW, "build"),
        (UPDATE_WORKFLOW, "propose"),
    ]:
        job = load(path)["jobs"][name]
        step = next(s for s in job["steps"] if "scripts/acquire_sources.py" in s.get("run", ""))
        assert step["env"]["SOURCE_TOKEN"] == "${{ steps.source-token.outputs.token }}"
        expected = "candidate" if path == UPDATE_WORKFLOW else "reviewed"
        assert f"--mode {expected}" in step["run"]
        assert "--output .source-checkouts" in step["run"]
        if path == UPDATE_WORKFLOW:
            assert step["if"] == "steps.existing.outputs.skip != 'true'"
        if path != UPDATE_WORKFLOW:
            checkout = next(
                s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@")
            )
            assert checkout["with"]["persist-credentials"] == "false"


def test_pages_has_explicit_release_controls():
    workflow = load(DEPLOY_WORKFLOW)
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {"group": "pages", "cancel-in-progress": "false"}
    assert set(workflow["on"]) == {"push", "workflow_dispatch"}
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert set(workflow["jobs"]) == {"build", "deploy"}
    deploy = workflow["jobs"]["deploy"]
    assert deploy["needs"] == "build"
    assert deploy["environment"]["name"] == "github-pages"
    build = workflow["jobs"]["build"]
    upload = next(
        s for s in build["steps"] if s.get("uses", "").startswith("actions/upload-pages-artifact@")
    )
    assert upload["with"]["path"] == "site"
    configure = next(
        s for s in build["steps"] if s.get("uses", "").startswith("actions/configure-pages@")
    )
    assert configure["with"]["enablement"] == "false"


def test_source_updates_are_review_only_proposals():
    workflow = load(UPDATE_WORKFLOW)
    assert set(workflow["on"]) == {"schedule", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["propose"]
    update = next(s for s in job["steps"] if "scripts/update_source_locks.py" in s.get("run", ""))
    assert "--skip-unapproved" in update["run"]
    proposal = next(s for s in job["steps"] if "gh pr create" in s.get("run", ""))
    assert proposal["if"] == "steps.changes.outputs.changed == 'true'"
    assert "git add docs-manifest.yml" in proposal["run"]
    assert "gh pr merge" not in proposal["run"]
    assert "git push" in proposal["run"]


def test_internal_guidance_stays_private_and_approvals_are_server_side():
    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text())
    assert "operations/" in config["exclude_docs"].splitlines()
    guide = (ROOT / "docs/operations/github_app.md").read_text()
    for term in [
        "docs-sources",
        "Required reviewers",
        "main",
        "branch",
        "repository-level",
        "organization-level",
        "cannot retrieve",
    ]:
        assert term in guide


def test_effective_job_permissions_have_narrow_write_boundaries():
    for path in (WORKFLOW, DEPLOY_WORKFLOW, UPDATE_WORKFLOW):
        workflow = load(path)
        for name, job in workflow["jobs"].items():
            effective = job.get("permissions", workflow["permissions"])
            if path == DEPLOY_WORKFLOW and name == "deploy":
                assert effective == {"contents": "read", "pages": "write", "id-token": "write"}
            elif path == UPDATE_WORKFLOW and name == "propose":
                assert effective == {"contents": "write", "pull-requests": "write"}
            else:
                assert effective == {"contents": "read"}


def test_browser_checks_gate_each_full_release():
    for path, name in [
        (WORKFLOW, "source-docs"),
        (DEPLOY_WORKFLOW, "build"),
        (UPDATE_WORKFLOW, "propose"),
    ]:
        job = load(path)["jobs"][name]
        assert_order(
            job, ["actions/setup-node@", "npm ci --ignore-scripts", "scripts/check_release.py"]
        )
        check = next(s for s in job["steps"] if "scripts/check_release.py" in s.get("run", ""))
        assert "--browser-tests" in check["run"]
        if path == UPDATE_WORKFLOW:
            for step in job["steps"]:
                if "actions/setup-node@" in step.get("uses", "") or "npm ci" in step.get("run", ""):
                    assert step["if"] == "steps.changes.outputs.changed == 'true'"
