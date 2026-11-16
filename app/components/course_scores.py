"""A compact, accessible confirmed/tentative score bar using native charts."""

import altair as alt
import streamlit as st


def show_score_bar(summary):
    confirmed, tentative, combined = (summary[name] for name in ("confirmed", "tentative", "combined"))
    if not combined["possible"]:
        st.caption("No graded assignment scores yet. Rocky's scores will appear here as tentative.")
        st.progress(0)
        return
    total = combined["possible"]
    remaining = max(0, total - combined["earned"])
    dark = st.context.theme.type == "dark"
    muted = "#344454" if dark else "#E0E5EB"
    data = [
        {"category": "Confirmed", "points": confirmed["earned"], "start": 0, "end": confirmed["earned"], "row": "Score"},
        {"category": "Tentative (Rocky)", "points": tentative["earned"],
         "start": confirmed["earned"], "end": combined["earned"], "row": "Score"},
        {"category": "Not earned", "points": remaining, "start": combined["earned"], "end": total, "row": "Score"},
    ]
    for segment in data:
        segment["percentage"] = segment["points"] / total * 100
    chart = alt.Chart(alt.Data(values=data)).mark_bar(size=16).encode(
        x=alt.X("start:Q", axis=None, scale=alt.Scale(domain=[0, total], nice=False)),
        x2=alt.X2("end:Q"),
        y=alt.Y("row:N", axis=None),
        color=alt.Color("category:N", scale=alt.Scale(
            domain=["Confirmed", "Tentative (Rocky)", "Not earned"], range=["#2D9B64", "#F59E0B", muted],
        ), legend=alt.Legend(title=None, orient="bottom", direction="horizontal")),
        tooltip=[alt.Tooltip("category:N", title="Status"), alt.Tooltip("points:Q", title="Points", format=".2f"),
                 alt.Tooltip("percentage:Q", title="% of graded points", format=".2f")],
    ).properties(height=20).configure(background="transparent").configure_view(stroke=None).configure_legend(
        labelColor="#FAFAFA" if dark else "#31333F",
    )
    # Keep the requested green/orange fills in both app themes.
    st.altair_chart(chart, width="stretch", theme=None)
    for column, label, values in zip(st.columns(3), ["Confirmed", "Tentative Rocky", "If confirmed"], [confirmed, tentative, combined]):
        percentage = round(values["earned"] / total * 100, 2)
        prefix = "+" if label == "Tentative Rocky" else ""
        score = f"{prefix}{values['earned']:g}/{total:g} · {prefix}{percentage:g}%"
        column.caption(f"**{label}**  \n{score}")
    st.caption("Green is confirmed. Orange shows the extra points if your professor confirms Rocky's current grades. "
               "Both use the same total of graded points; each assignment counts once.")
