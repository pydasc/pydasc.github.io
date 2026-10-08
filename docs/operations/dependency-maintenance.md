# Reproducing and reviewing the documentation environment

Python 3.13.16 is the release baseline, declared in `.python-version` and checked
against workflow setup steps. `requirements-docs.in` records direct intent;
`requirements-docs.txt` records the complete 32-package install lock, including
transitive dependencies. `requirements-dev.txt` adds only the pinned Ruff formatter.
No dependency versions were upgraded by this refactoring.

For a clean reproduction, create a disposable environment with Python 3.13.16:

```bash
python3.13 -m venv /tmp/dasc-web-environment
/tmp/dasc-web-environment/bin/python -m pip install -r requirements-dev.txt
/tmp/dasc-web-environment/bin/python -m pip check
/tmp/dasc-web-environment/bin/python scripts/check_dependencies.py
/tmp/dasc-web-environment/bin/python -m ruff format --check scripts tests
/tmp/dasc-web-environment/bin/python scripts/check_release.py --pydasc PATH --dasc PATH
```

`check_dependencies.py` compares installed metadata with all exact pins, direct
intent and active dependency constraints. It does not import upstream code or
remove transitive pins. The environment can contain extra development packages;
a clean environment is used to prove the lock itself is sufficient.

For a deliberate upgrade, record Python, OS/architecture and pip version, then
create a separate clean environment. Edit direct intent only after reviewing the
upstream release. Resolve there with `python -m pip install -r requirements-docs.in`,
record `python -m pip freeze --all`, and review the resulting exact dependency set
before replacing the lock. Separate installer tools such as pip from runtime pins.
Resolver output can vary with platform and index state; freeze is an auditable
review input, not a claim of a platform-independent solver lock or supply-chain
hash verification. Test the reviewed result on the Linux/macOS CI matrix.

Reproduction installs the reviewed lock, not an unconstrained re-resolution.
Version changes require all source-free tests, actual approved-source strict release
checks and the browser tests. Review theme override compatibility and the manual
accessibility checklist. A major MkDocs/Material migration is a separate decision.

The browser harness separately uses Node 24.19.0 and the exact `package-lock.json`.
Use `npm ci --ignore-scripts`; do not replace the lock with an unreviewed update.
