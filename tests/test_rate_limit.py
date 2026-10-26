"""Fixed-window limits, including exact limits and fractional-second boundaries."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from auth import rate_limit

pytestmark = [pytest.mark.unit, pytest.mark.regression]


@pytest.fixture
def clock_and_counter(monkeypatch):
    class Clock(datetime):
        current = datetime(2026, 10, 26, 12, 14, 59, 250000, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            assert tz == timezone.utc
            return cls.current

    counter = Mock(return_value={"attempts": 1})
    monkeypatch.setattr(rate_limit, "datetime", Clock)
    monkeypatch.setattr(rate_limit.db, "increment_one", counter)
    return Clock, counter


@pytest.mark.parametrize("attempts,expected", [(1, (True, 0)), (5, (True, 0)), (6, (False, 1))])
def test_limit_includes_fifth_attempt_and_rounds_retry_up(clock_and_counter, attempts, expected):
    _, counter = clock_and_counter
    counter.return_value = {"attempts": attempts}
    assert rate_limit.use_attempt("login", "ada@example.com") == expected


def test_counter_has_utc_window_metadata_and_rolls_over(clock_and_counter):
    clock, counter = clock_and_counter
    start = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    end = datetime(2026, 10, 26, 12, 15, tzinfo=timezone.utc)
    rate_limit.use_attempt("login", "ada@example.com")
    counter.assert_called_once_with(
        "rate_limits", f"login:ada@example.com:{int(start.timestamp())}", "attempts",
        on_insert={"action": "login", "identifier": "ada@example.com",
                   "window_start": start, "expires_at": end},
    )
    clock.current = end
    rate_limit.use_attempt("login", "ada@example.com")
    assert counter.call_args.args[1] == f"login:ada@example.com:{int(end.timestamp())}"


def test_custom_window_and_limit(clock_and_counter):
    clock, counter = clock_and_counter
    clock.current = datetime(2026, 10, 26, 12, 0, 10, 100000, tzinfo=timezone.utc)
    counter.return_value = {"attempts": 3}
    assert rate_limit.use_attempt("reset", "ada@example.com", limit=2, window_seconds=60) == (False, 50)
    assert counter.call_args.kwargs["on_insert"]["expires_at"] == datetime(
        2026, 10, 26, 12, 1, tzinfo=timezone.utc,
    )


@pytest.mark.parametrize("limit,window", [(0, 900), (-1, 900), (5, 0), (5, -1)])
def test_invalid_limits_never_increment(clock_and_counter, limit, window):
    _, counter = clock_and_counter
    with pytest.raises(ValueError, match="must be positive"):
        rate_limit.use_attempt("login", "ada@example.com", limit, window)
    counter.assert_not_called()
