"""A bounded background grader backed by durable MongoDB submission state.

No tasks or futures live in a student's session. Run inside Streamlit (default),
or set HOMEWORK_GRADING_WORKER=external and run `PYTHONPATH=app python -m
homework.worker` in an always-on process using the same database and Rocky keys.
"""

import logging
import os
from datetime import datetime, timezone
from threading import Event, Lock, Thread

from db.DataBase import db
from homework.grading import _grade_saved_submission, pending_grading_query

logger = logging.getLogger(__name__)
POLL_SECONDS = 5
_lock = Lock()
_thread = None


def process_next_submission(*, rocky_client=None, now=None):
    """Process at most one due attempt, oldest first, without a logged-in user."""
    query = pending_grading_query(now or datetime.now(timezone.utc))
    submission = db.read_one("homework_submissions", query, sort=[("submitted_at", 1), ("_id", 1)])
    if submission is None:
        return False
    _grade_saved_submission(submission, rocky_client=rocky_client, now=now, claim_filter=query)
    return True


def run_worker(stop=None):
    """Drain work serially; sleep when idle or after a database error."""
    stop = stop if stop is not None else Event()
    while not stop.is_set():
        try:
            if process_next_submission():
                continue
        except Exception as error:
            # Do not log private answers, references, or database exception text.
            # A failed final write is recovered when its lease expires.
            logger.warning("Homework grading worker will retry (%s)", type(error).__name__)
        stop.wait(POLL_SECONDS)


def start_grading_worker():
    """Start one daemon per app process, shared across sessions and reruns."""
    global _thread
    if os.getenv("HOMEWORK_GRADING_WORKER", "embedded") == "external":
        return
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = Thread(target=run_worker, name="homework-grading", daemon=True)
            _thread.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
