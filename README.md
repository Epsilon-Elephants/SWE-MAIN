# SWE-MAIN

## Automated tests

Install development dependencies and run the suite from the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

Run only the professor classes tests:

```bash
python -m pytest tests/test_professor_classes.py -v
```

Generate the same reports as CI:

```bash
python -m pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-report=html --junitxml=test-results.xml
```

Open `htmlcov/index.html` to browse coverage. Coverage is reported without a minimum
threshold while the suite grows.

The suite includes existing unittest tests and pytest regression tests. Pure logic
and database query tests use mocks; Streamlit UI tests use headless `AppTest`
without a browser or server. An automatic pytest fixture blocks live database
access, so no MongoDB service, `.env`, or GitHub secrets are needed. Mock database
operations explicitly when adding tests. These tests do not validate a real MongoDB
deployment or browser rendering.

## GitHub Actions setup

1. Commit and push `.github/workflows/tests.yml`, the test files, `pytest.ini`, and
   `requirements-dev.txt` along with this documentation and `.gitignore` changes.
2. Open a pull request. In its **Checks** tab, find **Python tests**. The workflow
   installs Python 3.12 and dependencies, then runs the entire suite. New commits
   to the PR rerun the tests. Pushes to any branch also run the suite, including
   the push created by merging a PR. A branch with an open PR can have both runs.
3. For failures, open **Actions → Tests → the run → Python tests** and expand
   **Run suite with coverage**. Download `test-reports` from the run's artifacts
   for JUnit results and HTML/XML coverage. A failed test makes the check fail.
4. To prevent merging failing PRs, open **Settings → Rules → Rulesets**, create a
   branch ruleset targeting your merge destination (for example `main` or `dev`),
   and set enforcement to **Active**. Enable **Require a pull request before
   merging** and **Require status checks to pass**. After the first workflow run,
   select **Python tests** as a required check. Enable requiring branches to be
   up to date if you want each PR checked against the latest destination branch.
   Review bypass permissions so the rule applies to the intended contributors.
5. Merge only after the required check passes. The post-merge push run verifies
   the resulting branch; it cannot undo a merge. The required PR check is what
   prevents a failing merge. Merge queue testing is also supported via
   `merge_group` if you enable a queue.

No workflow needs to be created manually in the Actions tab. GitHub discovers the
YAML file when it is pushed. If Actions is disabled, enable it under
**Settings → Actions → General**. Required-check availability depends on your
repository visibility and GitHub plan. Repository branch rules must be configured
by someone with appropriate GitHub permissions; adding workflow YAML alone does
not enforce them.

References: [GitHub status checks](https://docs.github.com/en/pull-requests/reference/status-checks)
and [required-check troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).
