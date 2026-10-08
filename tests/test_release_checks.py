from pathlib import Path
from types import SimpleNamespace
import subprocess
import pytest
from check_release import check, ReleaseCheckError


def options(tmp):
    docs = tmp / "docs"
    for name in ("pydasc", "dasc"):
        (docs / name).mkdir(parents=True)
        (docs / name / "index.md").write_text("unchanged")
    (docs / "generated-inventory.json").write_text("inventory")
    config = tmp / "mkdocs.yml"
    config.write_text("docs_dir: docs\n")
    return SimpleNamespace(
        config=config,
        docs=docs,
        site=tmp / "site",
        manifest=tmp / "manifest.yml",
        pydasc=tmp / "source-p",
        dasc=tmp / "source-d",
        skip_tests=True,
    )


@pytest.mark.parametrize("fail_at", range(1, 9))
def test_release_pipeline_stops_at_each_failed_stage(tmp_path, fail_at):
    opts = options(tmp_path)
    calls = []

    def runner(args, **kwargs):
        assert kwargs["check"] is True
        calls.append(args)
        if len(calls) == fail_at:
            raise subprocess.CalledProcessError(1, args)

    with pytest.raises(ReleaseCheckError, match="stage failed"):
        check(opts, runner)
    assert len(calls) == fail_at


def test_release_pipeline_rejects_nondeterministic_collection(tmp_path):
    opts = options(tmp_path)
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        if len(calls) == 4:
            (opts.docs / "pydasc/index.md").write_text("changed on repeat")

    with pytest.raises(ReleaseCheckError, match="repeated collection differs"):
        check(opts, runner)
    assert len(calls) == 4


def test_release_pipeline_includes_final_scan_and_no_deployment(tmp_path):
    stages = check(options(tmp_path), lambda *args, **kwargs: None)
    assert stages == [
        "collect",
        "validate-docs",
        "validate-physics",
        "collect-repeat",
        "strict-build",
        "validate-site",
        "validate-accessibility",
        "scan-artifact",
    ]
