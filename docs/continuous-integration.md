# Continuous Integration

The `Project CI` workflow runs on pull requests targeting `develop` or `main`, pushes to those branches, and manual dispatch. It has read-only repository permissions and cancels superseded runs for the same ref. It does not deploy or merge code.

## Checks

| Job | Coverage | External requirements |
| --- | --- | --- |
| Frontend | Node parser tests, both Vite builds, and dashboard save/delete browser regressions | Chromium is installed in the runner; dashboard API calls are mocked. |
| Python | JSON parsing, rerun classification, diagnostics, FastAPI handlers, and mocked Groq output | Installs the Python service requirements; no database server, browser binary, or real API key is required. |

The Python suite is deliberately discovered only under `python-services/tests`. Existing files in `test_scripts` are manual smoke scripts that can open a real browser/database. They are not CI unit tests.

These checks do not establish real PostgreSQL compatibility, production readiness, live provider quality, or complete website coverage. Add isolated database migration/integration jobs with the storage PR. Do not run authorized external write/security probes in PR CI.

The current Starlette TestClient emits a deprecation warning for its httpx integration. It does not fail these tests; a test-client dependency migration can be reviewed separately. This PR does not suppress the warning or change runtime dependencies.

## Reproduce locally

From the repository root, using Node 22 and Python 3.12 (CI versions):

```powershell
npm ci
npm test
npm run build -w apps/dashboard
npm run build -w apps/target-app
npx playwright install chromium
npm run test:requests -w apps/dashboard
```

In a Python virtual environment:

```powershell
python -m pip install -r python-services/requirements-test.txt
$env:PYTHONPATH = (Resolve-Path python-services).Path
python -X utf8 -m unittest discover -s python-services/tests -v
```

For Bash, replace the PowerShell environment assignment with `export PYTHONPATH="$PWD/python-services"`. UTF-8 mode keeps the existing Rich logger's symbols readable in Windows terminals. Keep credentials out of the shell history and repository. Groq tests replace the provider client and use a synthetic test key; CI supplies no real key.

## Branch dependency

This CI change is based on `bugfix/dashboard-save-delete`, which supplies the browser regression suite and depends on the dashboard-polish/build-fix work. Merge those dependencies first; the CI PR is not a replacement for them. Branch protection and required-check settings must be configured by a maintainer separately; a workflow file alone does not enforce approval or passing checks.
