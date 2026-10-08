from pathlib import Path
import pytest
import yaml
from check_dependencies import read_pins, ROOT


@pytest.mark.parametrize(
    "line",
    [
        "thing>=1",
        "thing==1.*",
        "thing @ https://example.org/a.whl",
        "thing==1; python_version > '3'",
        "thing[x]==1",
        "thing==1\nThing==1",
    ],
)
def test_dependency_lock_rejects_ambiguous_pins(tmp_path, line):
    path = tmp_path / "requirements.txt"
    path.write_text(line)
    with pytest.raises(ValueError):
        read_pins(path)


def test_direct_dependency_intent_agrees_with_lock():
    lock = read_pins(ROOT / "requirements-docs.txt")
    assert set(read_pins(ROOT / "requirements-docs.in").items()) <= set(lock.items())


def test_workflow_python_matches_reviewed_baseline():
    expected = (ROOT / ".python-version").read_text().strip()
    for file in (ROOT / ".github/workflows").glob("*.yml"):
        workflow = yaml.load(file.read_text(), Loader=yaml.BaseLoader)
        for job in workflow["jobs"].values():
            for step in job["steps"]:
                if step.get("uses", "").startswith("actions/setup-python@"):
                    assert step["with"]["python-version"] == expected
