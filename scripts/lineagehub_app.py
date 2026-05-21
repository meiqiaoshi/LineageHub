"""Local Streamlit demo for LineageHub (install with ``pip install -e \".[ui]\"``)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from lineagehub.db_path import default_db_path
from lineagehub.output import datasets_list_payload
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


_render_dataset_catalog(store)
