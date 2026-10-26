# SWE-MAIN

Streamlit application for professor-managed classes, short-answer homework, and
the Rocky AI assistant. Students can submit homework and review their attempts.
Homework is saved as **ungraded**; automatic grading is not connected yet.

## Documentation

- [Local setup and development](docs/development.md): configuration, running the app, tests, and common setup issues.
- [How the application works](docs/architecture.md): navigation, responsibilities, collections, and access rules.
- [Problem format and AI integration](docs/ai-grading.md): problem fields, a complete grading-input example, the Rocky client, and work remaining for grading.
- [Assignments and submissions](docs/assignments.md): dates, authoring helpers, submission history, and database validation.
- [Problem JSON Schema](docs/homework-problem.schema.json): the canonical v1 problem document.

## Quick start

Use Python 3.12 (the version used in CI), then run from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Fill in `DB_URI` and `DB_NAME` in `.env`, then start the app:

```bash
python -m streamlit run app/app.py
```

Set `ROCKY_KEY` to use the AI assistant. See the setup guide for account roles
and database preparation.

## Testing

Activate your virtual environment and run these commands from the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

Tests use **pytest** for isolated Python logic and mocked persistence, and
Streamlit's [AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)
for existing page regressions. No running app, browser, `.env`, MongoDB instance,
or Rocky token is required. The shared fixtures reject live MongoDB access and
HTTP requests; mock the database helper or HTTP call when adding tests.

Run a selected group or a single file:

```bash
python -m pytest -m unit
python -m pytest -m regression
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_rate_limit.py -k rolls_over -v
```

`unit` selects isolated function and data-contract checks. `regression` selects
checks protecting existing application rules and flows. A test can carry both
markers; the default command runs every test once. Regression cases protect the
current implementation and do not imply that a bug was previously reported.

| Area | Checks |
| --- | --- |
| Authentication | Real password hashing and verification, registration validation, normalized identity, supported roles, throttled login, and database errors. |
| Rate limiting | Exact attempt limit, UTC window rollover, retry rounding, custom windows, and atomic counter query. |
| Assignments and problems | Required fields, dates, drafts/publication, ownership filters, stable problem IDs, edits/deletion, schema validation, and grading-input snapshots. |
| Classes and grades | Professor ownership, enrollment, grade validation, literal searches, pagination, and class-scoped roster queries. |
| Homework | Student access, answer validation, ungraded submission history, and private instructor fields staying out of student pages. |
| Rocky and pages | Mocked HTTP/stream handling, topic analysis, and existing dashboard/settings/navigation regressions through AppTest. |

Generate the same reports as CI:

```bash
python -m pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-report=html --junitxml=test-results.xml
```

Open `htmlcov/index.html` for line coverage. `coverage.xml` and `test-results.xml`
are machine-readable reports. These generated files are ignored by Git. CI also
uploads them as the `test-reports` artifact.

Add tests under `tests/test_*.py`, mark them with `@pytest.mark.unit` and/or
`@pytest.mark.regression` (or module-level `pytestmark`), and use fixtures from
`tests/conftest.py`. Assert results and rejected writes, including boundary and
failure cases. Mock external services rather than using development accounts.

These tests do not verify a real MongoDB deployment, Rocky availability, browser
rendering, or end-to-end user acceptance. Browser/behavioral testing is deferred
to a later phase. [Playwright for Python](https://playwright.dev/python/docs/intro)
with Chromium can extend this pytest setup then; Playwright and browser binaries
are not currently dependencies or required test steps.

## Pull requests

1. Push your branch and open a pull request.
2. Wait for **Python tests** in the PR’s **Checks** tab to pass. Tests run automatically.
3. If tests fail, open the failed check to see the errors, fix them, and push again.
4. Merge once tests pass and required reviews are complete.
