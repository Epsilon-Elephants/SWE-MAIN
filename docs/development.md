# Local setup and development

## Install and run

Run commands from the repository root. CI uses Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

`requirements-dev.txt` includes the application requirements plus pytest and
coverage tools. To install only application dependencies, use `requirements.txt`.
On Windows, activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell.

Fill in the local `.env` using these names:

| Name | Purpose |
| --- | --- |
| `DB_URI` | MongoDB connection URI for the intended local/development database. |
| `DB_NAME` | Database name within that MongoDB deployment. |
| `ROCKY_KEY` | Bearer token for the student Rocky assistant. Not needed to save ungraded homework. |

The database helper loads `.env` on first database access. The student Rocky
caller loads it before constructing the client. Environment values take
precedence over fallback values in Streamlit secrets. Do not put real credentials
in `.env.example` or documentation; `.env` is ignored by Git.

Streamlit deployments can supply the same keys through Streamlit secrets. If you
create a local `.streamlit/secrets.toml`, keep it out of Git; `.gitignore`
explicitly excludes that file and local environment variants.

```bash
python -m streamlit run app/app.py
```

Use the local URL printed by Streamlit. Launching `app/app.py` as an ordinary
Python script does not start the Streamlit application.

Application dependencies have version bounds, including an explicit `requests`
dependency for Rocky. Streamlit 1.63 or newer is required for the registered page
visibility and UI APIs used here. The theme lives in `.streamlit/config.toml` and
uses built-in fonts. A lockfile is not supplied yet.

## Accounts and database preparation

Public registration creates students. There is no public professor signup or
role-promotion screen. A development professor account must have
`permissions: "professor"` provisioned in MongoDB by someone managing that
database. Classes must reference that user's ObjectId in `instructor_id` for
ownership checks to work. The repository does not include a complete seed script.

Professors can enroll existing students into their own classes. Enrollment is
stored in `students` as a relationship between a user and a class. A student
without enrollments or posted homework will see an empty homework list.

For assignment/submission database validation, open `mongosh` against the intended
database, with the shell's working directory at the repository root, and run:

```javascript
load("docs/assignment-validation.js")
```

This script changes database validators and creates assignment/submission indexes;
it is a manual database setup action, not an app-startup step. It does not seed
users/classes, backfill old records, or check cross-collection relationships.
See [Assignments and submissions](assignments.md) before applying it.

## Tests

Install `requirements-dev.txt` and run from the repository root:

```bash
python -m pytest
python -m pytest -m unit
python -m pytest -m regression
```

The markers overlap: unit tests isolate functions and data contracts, while
regression tests protect current application rules and flows. Running the full
suite executes each test once. See the [README testing guide](../README.md#testing)
for coverage scope, adding tests, and the future Playwright/Chromium phase.

To run only the problem-format and submission-flow regressions:

```bash
python -m pytest tests/test_homework.py
```

To run the same coverage command as CI:

```bash
python -m pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-report=html --junitxml=test-results.xml
```

`tests/conftest.py` exposes the `app/` import path and blocks live MongoDB and HTTP
access for the default test suite. Tests mock database operations; Rocky tests
mock HTTP requests. Existing Streamlit page regressions use `AppTest`. Running
the suite does not require `.env`, live credentials, an app server, or a browser.
Playwright is not installed in this phase; browser/behavioral tests are deferred.

CI runs on pushes, pull requests, merge groups, and manual dispatch, and uploads
coverage/test reports as the `test-reports` artifact. Passing these mocked tests
does not verify live database configuration or Rocky availability.

## Common setup issues

| Symptom | What to check |
| --- | --- |
| Missing database secrets or unavailable login | Supply both `DB_URI` and `DB_NAME`; check connectivity and database credentials. |
| No professor dashboard | Public signup always creates students; check the provisioned role and sign in again after changing it. |
| Professor cannot use a class | Check that `classes.instructor_id` is the professor's BSON ObjectId. |
| Student has no homework | Check enrollment, assignment status, and posted date. Date-only inputs become midnight UTC. |
| Rocky unavailable | Check `ROCKY_KEY`, endpoint connectivity, and server logs. Homework submission itself does not call Rocky. |
| Tests attempt to connect to MongoDB | Mock the relevant database helper; the test fixture intentionally rejects live connections. |
| Tests attempt a live HTTP request | Mock the HTTP call (for example, Rocky's `requests.get`/`requests.post`); the shared fixture intentionally blocks real requests. |

For changes to the grading contract, update [the AI guide](ai-grading.md),
[problem JSON Schema](homework-problem.schema.json), and normalization/tests
together. Keep implemented behavior distinct from planned grading features.
