from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.blackboard import ConversationState
from src.catalog import Catalog, ListingFilters
from src.orchestrator import Orchestrator

st.set_page_config(page_title="Amsterdam Listings Agents", page_icon="🚲", layout="wide")

EXAMPLES = [
    "Find deals in De Pijp under 280 euros",
    "Guide to Westerpark",
    "Find a canal apartment in De Pijp under 300 euros for 3 nights",
    "Compare De Pijp and Westerpark",
    "Plan a 4-night trip with total budget 900",
    "Recommend top 5 scored private rooms near the center",
    "save top",
    "show watchlist",
    "explain top",
    "similar",
    "help",
]


@st.cache_resource
def get_orchestrator() -> Orchestrator:
    csv_path = Path(__file__).resolve().parent / "listings.csv"
    return Orchestrator(Catalog.load(csv_path))


def render_result(result) -> None:
    stage = getattr(result, "stage", "specialist")
    st.markdown(f"#### {result.title}")
    st.caption(f"agent `{result.agent}` · stage `{stage}`")
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


def briefing_markdown(results: list) -> str:
    chunks = []
    for result in results:
        chunks.append(f"## {result.title} (`{result.agent}`)\n\n{result.markdown}")
    return "\n\n".join(chunks)


orch = get_orchestrator()
snap = orch.catalog.snapshot()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi! Multi-stage agents over Amsterdam listings: deals, guides, watchlists, "
                "explanations, search, compare, and trip budgets. Try `Find deals in De Pijp`, "
                "`Guide to Westerpark`, or `save top` after a shortlist."
            ),
            "results": [],
            "trace": [],
            "plan": [],
        }
    ]
if "conversation" not in st.session_state:
    st.session_state.conversation = ConversationState()

with st.sidebar:
    st.header("Amsterdam listings")
    c1, c2 = st.columns(2)
    c1.metric("Listings", f"{snap['rows']:,}")
    c2.metric("With price", f"{snap['priced']:,}")
    c3, c4 = st.columns(2)
    c3.metric("Median", f"€{snap['median_price']:.0f}" if snap["median_price"] else "n/a")
    c4.metric("Licensed", f"{snap['licensed']:,}")
    st.caption(memory_caption(st.session_state.conversation.filters))
    if st.session_state.conversation.last_listing_ids:
        st.caption("Shortlist: " + ", ".join(map(str, st.session_state.conversation.last_listing_ids[:6])))
    st.caption(f"Watchlist ({len(st.session_state.conversation.watchlist)}): "
               + (", ".join(map(str, st.session_state.conversation.watchlist[:8])) or "empty"))
    st.caption(f"Turn {st.session_state.conversation.turn}")
    if st.button("Clear chat & memory", use_container_width=True):
        st.session_state.messages = [st.session_state.messages[0]]
        st.session_state.conversation = ConversationState()
        st.rerun()
    st.divider()
    st.write("Pipeline")
    st.code("planner → specialists\n→ fallback?\n→ critique → synthesize", language=None)
    st.divider()
    st.write("Examples")
    for q in EXAMPLES:
        if st.button(q, use_container_width=True):
            st.session_state["_pending"] = q

st.title("Amsterdam listings multi-agent guide")
st.write(
    "Specialists now include **deal**, **guide**, **explain**, and **watchlist**, "
    "on top of search / insights / compare / budget / host / similar, "
    "coordinated through a blackboard pipeline."
)

pending = st.session_state.pop("_pending", None)
prompt = st.chat_input("Ask about deals, guides, watchlist, budget, compare…")
user_text = pending or prompt

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("plan"):
            st.caption("plan: " + " → ".join(msg["plan"]))
        for result in msg.get("results") or []:
            render_result(result)
        if msg.get("trace"):
            st.caption("route: " + " → ".join(msg["trace"]))
        if msg.get("export"):
            st.download_button(
                "Download turn briefing",
                data=msg["export"],
                file_name="ams-listings-briefing.md",
                mime="text/markdown",
                key=f"dl-{hash(msg['export']) % 10_000_000}",
            )

if user_text:
    st.session_state.messages.append(
        {"role": "user", "content": user_text, "results": [], "trace": [], "plan": []}
    )
    with st.chat_message("user"):
        st.markdown(user_text)

    response = orch.handle(user_text, conversation=st.session_state.conversation)
    st.session_state.conversation = response.conversation
    export = briefing_markdown(response.results)

    assistant_text = (
        f"Pipeline plan: **{' → '.join(response.plan)}**. "
        f"Full route: **{' → '.join(response.trace)}**."
    )
    with st.chat_message("assistant"):
        st.markdown(assistant_text)
        synth = [r for r in response.results if r.agent == "synthesize"]
        rest = [r for r in response.results if r.agent != "synthesize"]
        for result in synth + rest:
            render_result(result)
        st.caption("route: " + " → ".join(response.trace))
        st.caption(memory_caption(st.session_state.conversation.filters))
        st.download_button(
            "Download turn briefing",
            data=export,
            file_name="ams-listings-briefing.md",
            mime="text/markdown",
            key=f"dl-live-{st.session_state.conversation.turn}",
        )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": assistant_text,
            "results": response.results,
            "trace": response.trace,
            "plan": response.plan,
            "export": export,
        }
    )
