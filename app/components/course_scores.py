"""A compact, accessible confirmed/tentative score bar using native charts."""

import altair as alt
import streamlit as st


def show_score_bar(summary):
    confirmed, tentative, combined = (summary[name] for name in ("confirmed", "tentative", "combined"))
    if not combined["possible"]:
        st.caption("No graded assignment scores yet. Rocky's scores will appear here as tentative.")
        st.progress(0)
        return
    remaining = max(0, combined["possible"] - combined["earned"])
    muted = "#344454" if st.context.theme.type == "dark" else "#E0E5EB"
    data = [
        {"category": "Confirmed", "points": confirmed["earned"], "order": 0, "row": "Score"},
        {"category": "Tentative (Rocky)", "points": tentative["earned"], "order": 1, "row": "Score"},
        {"category": "Not earned", "points": remaining, "order": 2, "row": "Score"},
    ]
    chart = alt.Chart(alt.Data(values=data)).mark_bar(size=16).encode(
        x=alt.X("points:Q", stack="zero", axis=None, scale=alt.Scale(domain=[0, combined["possible"]], nice=False)),
        y=alt.Y("row:N", axis=None),
        color=alt.Color("category:N", scale=alt.Scale(
            domain=["Confirmed", "Tentative (Rocky)", "Not earned"], range=["#2D9B64", "#D59A25", muted],
        ), legend=alt.Legend(title=None, orient="bottom", direction="horizontal")),
        order=alt.Order("order:Q"),
        tooltip=[alt.Tooltip("category:N", title="Status"), alt.Tooltip("points:Q", title="Points", format=".2f")],
    ).properties(height=20).configure_view(stroke=None)
    st.altair_chart(chart, width="stretch")
    for column, label, values in zip(st.columns(3), ["Confirmed", "Tentative Rocky", "With tentative"], [confirmed, tentative, combined]):
        score = (f"{values['earned']:g}/{values['possible']:g} · {values['percentage']:g}%"
                 if values["possible"] else ("Awaiting confirmation" if label == "Confirmed" else "No tentative scores"))
        column.caption(f"**{label}**  \n{score}")
    st.caption("Based on scored assignments. Confirmed scores count toward your grade; tentative scores await professor confirmation. Each assignment counts once.")
