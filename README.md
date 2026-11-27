# LogiCourse

A Streamlit web app for logic and philosophy courses at Kent State, built by
Epsilon Elephants.

- **Professors** create courses and short-answer assignments. They review the
  grades suggested by Rocky, the AI assistant, then confirm or adjust them.
- **Students** complete assignments, see tentative and confirmed scores, and get
  practice suggestions on the topics where they need work.

Rocky grades each answer against the professor's reference answer and rubric.
Its scores stay tentative until a professor confirms them.

## Quick start

Requires Python 3.12 and a MongoDB database.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # set DB_URI, DB_NAME, and ROCKY_KEY
streamlit run app/app.py
```

## Tests

```bash
python -m pytest
```

Tests need no database, network access, or API key.

## Docs

- [Local setup and development](docs/development.md)
- [How the app works](docs/architecture.md)
- [AI grading](docs/ai-grading.md)
- [Assignments and submissions](docs/assignments.md)
- [Dashboard analytics](docs/analytics.md)
