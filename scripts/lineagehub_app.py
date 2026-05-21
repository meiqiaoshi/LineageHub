"""Local Streamlit demo for LineageHub (install with ``pip install -e \".[ui]\"``)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from lineagehub.db_path import default_db_path
from lineagehub.output import dataset_show_for_name, datasets_list_payload
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


_render_dataset_catalog(store)
_render_dataset_detail(store)
