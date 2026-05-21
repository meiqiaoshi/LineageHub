"""Local Streamlit demo for LineageHub (install with ``pip install -e \".[ui]\"``)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from lineagehub.db_path import default_db_path
from lineagehub.graph import collect_graph_edges
from lineagehub.output import (
    dataset_show_for_name,
    datasets_list_payload,
    format_edges_dot,
    incidents_rank_for_store,
    job_show_for_name,
    jobs_list_payload,
)
from lineagehub.store import MetadataStore

st.set_page_config(page_title="LineageHub", page_icon="🔗", layout="wide")

st.title("LineageHub")
st.markdown(
    "Local-first lineage and operational metadata browser. "
    "Load sample data with the CLI, then explore catalog, graph, and incidents here."
)

db_path = st.sidebar.text_input("Database path", value=default_db_path())
db_file = Path(db_path)

if not db_file.is_file():
    st.sidebar.error("Database file not found.")
    st.info(
        "Create a database and load examples:\n\n"
        "```bash\n"
        "lineagehub load examples/sample_lineage.json\n"
        "lineagehub load-runs examples/sample_runs.json\n"
        "```"
    )
    st.stop()

store = MetadataStore(str(db_file))
st.sidebar.success(f"Connected: `{db_path}`")


def _render_dataset_catalog(store: MetadataStore) -> None:
    payload = datasets_list_payload(store.list_dataset_records())
    st.subheader("Dataset catalog")
    if payload["count"] == 0:
        st.write("No datasets in this database.")
        return
    st.dataframe(payload["datasets"], use_container_width=True, hide_index=True)


def _render_dataset_detail(store: MetadataStore) -> None:
    names = sorted(d.name for d in store.list_datasets())
    if not names:
        return
    st.subheader("Dataset detail")
    selected = st.selectbox("Dataset", names, key="dataset_detail_select")
    try:
        detail = dataset_show_for_name(store, selected)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.json(detail["dataset"])
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Producer jobs**")
        st.write(detail["producer_jobs"] or "—")
        st.markdown("**Upstream**")
        if detail["upstream"]:
            st.dataframe(detail["upstream"], hide_index=True)
        else:
            st.write("—")
    with col2:
        st.markdown("**Consumer jobs**")
        st.write(detail["consumer_jobs"] or "—")
        st.markdown("**Downstream**")
        if detail["downstream"]:
            st.dataframe(detail["downstream"], hide_index=True)
        else:
            st.write("—")


def _render_job_catalog(store: MetadataStore) -> None:
    payload = jobs_list_payload(store.list_jobs())
    st.subheader("Job catalog")
    if payload["count"] == 0:
        st.write("No jobs in this database.")
        return
    st.dataframe(payload["jobs"], use_container_width=True, hide_index=True)


def _render_job_detail(store: MetadataStore) -> None:
    names = sorted(j.name for j in store.list_jobs())
    if not names:
        return
    st.subheader("Job detail")
    selected = st.selectbox("Job", names, key="job_detail_select")
    try:
        detail = job_show_for_name(store, selected)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.json(detail["job"])
    st.markdown("**Inputs**")
    st.write(detail["inputs"] or "—")
    st.markdown("**Outputs**")
    st.write(detail["outputs"] or "—")
    st.markdown(f"**Run count:** {detail['run_count']}")
    if detail["latest_run"]:
        st.markdown("**Latest run**")
        st.json(detail["latest_run"])


def _render_lineage_graph(store: MetadataStore) -> None:
    names = sorted(d.name for d in store.list_datasets())
    if not names:
        st.write("No datasets available for graph view.")
        return
    st.subheader("Lineage graph")
    dataset = st.selectbox("Root dataset", names, key="graph_dataset")
    direction = st.radio("Direction", ["downstream", "upstream", "both"], horizontal=True)
    depth = st.radio("Depth", ["all", "direct"], horizontal=True)
    try:
        edges = collect_graph_edges(
            store,
            dataset,
            direction=direction,  # type: ignore[arg-type]
            depth=depth,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    if not edges:
        st.write("No edges in this subgraph.")
        return
    dot = format_edges_dot(edges)
    with st.expander("DOT source"):
        st.code(dot, language="text")
    try:
        st.graphviz_chart(dot, use_container_width=True)
    except Exception:
        st.caption("Graphviz rendering unavailable; showing edge list.")
        st.dataframe(
            [{"upstream": u, "downstream": v} for u, v in edges],
            use_container_width=True,
            hide_index=True,
        )


def _render_incidents(store: MetadataStore) -> None:
    st.subheader("Incident ranking")
    limit = st.slider("Max ranked incidents", min_value=1, max_value=50, value=10)
    payload = incidents_rank_for_store(store, status="failed", limit_ranked=limit)
    if not payload["incidents"]:
        st.write("No failed runs to rank.")
        return
    st.dataframe(payload["incidents"], use_container_width=True, hide_index=True)


st.divider()
_render_dataset_catalog(store)
_render_dataset_detail(store)
st.divider()
_render_job_catalog(store)
_render_job_detail(store)
st.divider()
_render_lineage_graph(store)
st.divider()
_render_incidents(store)
