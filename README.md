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

## Pull requests

1. Push your branch and open a pull request.
2. Wait for **Python tests** in the PR’s **Checks** tab to pass. Tests run automatically.
3. If tests fail, open the failed check to see the errors, fix them, and push again.
4. Merge once tests pass and required reviews are complete.

To run tests locally before pushing:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```
