"""Grouped grade views that stay short as classes grow.

Instead of one row per attempt, show one row per student (or per assignment)
with the grade that counts, and keep every attempt in a dropdown under it.
The counted grade follows homework.grades.kept_attempt: a professor decision,
otherwise the highest Rocky score.
"""

from math import ceil

import streamlit as st

from homework.grades import attempt_score, group_attempts, kept_attempt
from homework.results import grading_label
from components.course_cards import status_color

PAGE_SIZE = 10
FILTERS = ("All", "Needs review", "Confirmed")


def _utc(value):
    return value.strftime("%b %d, %Y %H:%M UTC") if hasattr(value, "strftime") else ""


def kept_summary(attempts):
    """(kept attempt or None, short label, badge color) for one group of attempts."""
    kept = kept_attempt(attempts)
    score = attempt_score(kept)
    if score:
        earned, possible, confirmed = score
        source = "Confirmed" if confirmed else "Highest"
        return kept, f"{source} {earned:g}/{possible:g} · {100 * earned / possible:.0f}%", "green" if confirmed else "yellow"
    if any(row.get("grading_status") in {"ungraded", "grading", None} for row in attempts):
        return None, "Processing", "gray"
    return None, "Not graded", "gray"


def needs_review(attempts):
    """True until the professor confirms or overrides a grade for this group."""
    score = attempt_score(kept_attempt(attempts))
    return not (score and score[2])


def kept_percentage(attempts):
    score = attempt_score(kept_attempt(attempts))
    return None if not score else round(100 * score[0] / score[1], 1)


def _move(key, offset):
    st.session_state[key] = st.session_state.get(key, 0) + offset


def paginate(items, *, key, size=PAGE_SIZE):
    """Return this page's items and draw Previous/Next controls when needed."""
    pages = max(1, ceil(len(items) / size))
    page = min(max(0, st.session_state.get(key, 0)), pages - 1)
    st.session_state[key] = page
    if pages > 1:
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.button("Previous", key=f"{key}_previous", icon=":material/chevron_left:", type="tertiary",
                      disabled=page == 0, on_click=_move, args=(key, -1))
            st.caption(f"Page {page + 1} of {pages}")
            st.button("Next", key=f"{key}_next", icon=":material/chevron_right:", type="tertiary",
                      disabled=page >= pages - 1, on_click=_move, args=(key, 1))
    return items[page * size:(page + 1) * size]


def attempt_groups(rows, *, group_by, title_of, key, attempt_action, noun="student",
                   format_time=_utc, review_filters=True, empty="No submissions yet."):
    """One expandable row per group; the header shows the counted grade.

    group_by:       field to group on ("user_id" for students, "assignment_id" for work)
    title_of:       attempts -> display name for the group
    attempt_action: (attempt) -> None, draws the button(s) for one attempt
    """
    groups = group_attempts(rows, group_by)
    if not groups:
        st.caption(empty)
        return
    entries = sorted(((title_of(attempts), attempts) for attempts in groups.values()),
                     key=lambda entry: entry[0].casefold())
    pending = sum(needs_review(attempts) for _, attempts in entries)

    with st.container(horizontal=True, vertical_alignment="bottom"):
        query = st.text_input(f"Find a {noun}", key=f"{key}_search", placeholder=f"Search by {noun} name",
                              icon=":material/search:").strip().casefold()
        status = st.segmented_control("Show", FILTERS, default="All", required=True, key=f"{key}_filter") \
            if review_filters else "All"
    entries = [entry for entry in entries if query in entry[0].casefold()
               and (status == "All" or needs_review(entry[1]) == (status == "Needs review"))]
    attempts_total = sum(len(attempts) for _, attempts in groups.items())
    summary = f"{len(groups)} {noun}{'s' if len(groups) != 1 else ''} · {attempts_total} attempt{'s' if attempts_total != 1 else ''}"
    st.caption(summary + (f" · {pending} awaiting your review" if review_filters and pending else ""))
    if not entries:
        st.caption(f"No {noun}s match this search.")
        return

    for name, attempts in paginate(entries, key=f"{key}_page"):
        attempts = sorted(attempts, key=lambda row: (row.get("submitted_at") is not None, row.get("submitted_at")), reverse=True)
        kept, label, color = kept_summary(attempts)
        count = f"{len(attempts)} attempt{'s' if len(attempts) != 1 else ''}"
        with st.expander(f"**{name}** · {count} · :{color}-badge[{label}]",
                         key=f"{key}_group_{attempts[0].get(group_by)}"):
            for number, attempt in enumerate(attempts):
                with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                    st.caption(f"Attempt {len(attempts) - number} · {format_time(attempt.get('submitted_at'))}")
                    st.badge(grading_label(attempt), color=status_color(grading_label(attempt)))
                    if kept is not None and attempt.get("_id") == kept.get("_id"):
                        st.badge("Counts", icon=":material/star:", color="green",
                                 help="This attempt counts toward the grade: the professor's decision, "
                                      "otherwise the highest Rocky score.")
                    st.space("stretch")
                    attempt_action(attempt)
