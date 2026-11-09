"""Exercise Streamlit startup without pytest's preloaded application modules."""

from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.regression
@pytest.mark.parametrize("mode", ["imports", "login"])
def test_fresh_streamlit_process_with_app_directory_first(mode):
    root = Path(__file__).resolve().parents[1]
    script = textwrap.dedent('''
        from pathlib import Path
        import sys

        root = Path(sys.argv[1])
        mode = sys.argv[2]
        # Streamlit exposes the entrypoint's directory first. In that layout,
        # `import app` resolves app/app.py, not the repository namespace package.
        sys.path[:0] = [str(root / "app"), str(root)]
        assert "app" not in sys.modules

        import pymongo
        import requests
        from db.DataBase import db

        def unexpected_service(*args, **kwargs):
            raise AssertionError("Startup must not contact MongoDB or HTTP services.")

        pymongo.MongoClient = unexpected_service
        requests.sessions.Session.request = unexpected_service
        db._get_db = unexpected_service

        if mode == "imports":
            from homework import grading
            from rocky import data_adapter, recommendation
            from rocky.grading import InvalidGrade, grade_with_rocky

            assert grading.InvalidGrade is InvalidGrade
            assert grading.grade_with_rocky is grade_with_rocky
            assert "pages.welcome" not in sys.modules
        else:
            from streamlit.testing.v1 import AppTest

            app = AppTest.from_file(str(root / "app/app.py"), default_timeout=10).run()
            assert not app.exception, [error.message for error in app.exception]
            assert [title.value for title in app.title] == ["Welcome"]
            assert {button.label for button in app.button} >= {"Log in", "Create account"}

        assert "app" not in sys.modules, "A business-module import executed app/app.py."
        print(f"Fresh-process {mode} check passed.")
    ''')
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(root), mode],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Fresh-process {mode} check passed." in result.stdout
