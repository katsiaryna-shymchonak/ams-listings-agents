from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.catalog import Catalog, ListingFilters
from src.orchestrator import Orchestrator

st.set_page_config(page_title="Amsterdam Listings Agents", page_icon="🚲", layout="wide")

EXAMPLES = [
    "Find a canal apartment in De Pijp under 300 euros",
    "Compare neighbourhoods by price",
    "Recommend top 5 cheap private rooms near the center",
    "Average price in Westerpark",
    "What does host Edwin list?",
    "Find listings between 150 and 250 euros with terrace",
    "Show licensed apartments in Centrum-West",
    "help",
]


@st.cache_resource
def get_orchestrator() -> Orchestrator:
    csv_path = Path(__file__).resolve().parent / "listings.csv"
    return Orchestrator(Catalog.load(csv_path))


def render_result(result) -> None:
    st.markdown(f"#### {result.title}")
    st.caption(f"agent `{result.agent}`")
    st.markdown(result.markdown)
    if result.chart is not None and not result.chart.empty:
        if result.chart_kind == "neigh_price":
            st.bar_chart(result.chart.set_index("neighbourhood")["median_price"])
        elif "bucket" in result.chart.columns and "count" in result.chart.columns:
            st.bar_chart(result.chart.set_index("bucket")["count"])
    if result.table is not None and not result.table.empty:
        st.dataframe(result.table, use_container_width=True, hide_index=True)
    if result.map_points is not None and not result.map_points.empty:
        mp = result.map_points.rename(columns={"latitude": "lat", "longitude": "lon"})
        st.map(mp, latitude="lat", longitude="lon", size=40)


def memory_caption(memory: ListingFilters | None) -> str:
    if not memory:
        return "No remembered filters"
    data = memory.as_dict()
    if not data:
        return "No remembered filters"
    return "Remembered: " + ", ".join(f"{k}={v}" for k, v in data.items())


orch = get_orchestrator()
snap = orch.catalog.snapshot()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi! Ask about Amsterdam listings — neighbourhood, budget, keywords like "
                "`canal` / `terrace`, hosts, or market stats. Filters carry over across short follow-ups; "
                "say `reset` to clear them."
            ),
            "results": [],
            "trace": [],
        }
    ]
if "filter_memory" not in st.session_state:
    st.session_state.filter_memory = None

with st.sidebar:
    st.header("Amsterdam listings")
    c1, c2 = st.columns(2)
    c1.metric("Listings", f"{snap['rows']:,}")
    c2.metric("With price", f"{snap['priced']:,}")
    c3, c4 = st.columns(2)
    c3.metric("Median", f"€{snap['median_price']:.0f}" if snap["median_price"] else "n/a")
    c4.metric("Licensed", f"{snap['licensed']:,}")
    st.caption(memory_caption(st.session_state.filter_memory))
    if st.button("Clear chat & memory", use_container_width=True):
        st.session_state.messages = [st.session_state.messages[0]]
        st.session_state.filter_memory = None
        st.rerun()
    st.divider()
    st.write("Room types")
    st.json(snap["room_types"])
    st.divider()
    st.write("Examples")
    for q in EXAMPLES:
        if st.button(q, use_container_width=True):
            st.session_state["_pending"] = q

st.title("Amsterdam listings multi-agent guide")
st.write(
    "Five agents over `listings.csv`: **search**, **insights**, **recommend**, **host**, **help**. "
    "The orchestrator routes each turn and can call more than one agent."
)

pending = st.session_state.pop("_pending", None)
prompt = st.chat_input("Ask about neighbourhood, price, keywords, host, or the market…")
user_text = pending or prompt

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for result in msg.get("results") or []:
            render_result(result)
        if msg.get("trace"):
            st.caption("route: " + " → ".join(msg["trace"]))

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text, "results": [], "trace": []})
    with st.chat_message("user"):
        st.markdown(user_text)

    response = orch.handle(user_text, memory=st.session_state.filter_memory)
    st.session_state.filter_memory = response.memory

    assistant_text = f"Agents used: **{', '.join(response.trace)}**."
    with st.chat_message("assistant"):
        st.markdown(assistant_text)
        for result in response.results:
            render_result(result)
        st.caption("route: " + " → ".join(response.trace))
        st.caption(memory_caption(st.session_state.filter_memory))

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": assistant_text,
            "results": response.results,
            "trace": response.trace,
        }
    )
