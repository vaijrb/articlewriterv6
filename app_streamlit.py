"""
Streamlit UI for the Journal Article Writer. Run with: streamlit run app_streamlit.py
"""

import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from articlewriter.orchestrator import ArticleWriterPipeline
from articlewriter.exceptions import ArticleWriterError

st.set_page_config(page_title="Journal Article Writer", layout="wide")

st.title("Journal Article Writer")
st.markdown("Automated scholarly article generation: trends → retrieval → synthesis → article → plagiarism check → APA output.")

with st.sidebar:
    st.header("Settings")
    skip_trends = st.checkbox("Skip trend detection (use retrieval only)", value=False)
    write_pdf = st.checkbox("Generate PDF", value=True)
    custom_title = st.text_input("Article title (optional)", value="")
    run_full = st.button("Run full pipeline")

if run_full:
    with st.spinner("Running pipeline…"):
        try:
            pipeline = ArticleWriterPipeline()
            paths = pipeline.run_full(
                article_title=custom_title or None,
                write_pdf=write_pdf,
                skip_trends=skip_trends,
            )
            st.success("Pipeline completed.")
            for name, path in paths.items():
                st.write(f"**{name}**: `{path}`")
                if path.exists() and path.suffix == ".json":
                    with open(path, encoding="utf-8") as f:
                        st.json(f.read())
        except ArticleWriterError as e:
            st.error(str(e))

st.info("Configure API keys in `.env` (OPENAI_API_KEY, optional SEMANTIC_SCHOLAR_API_KEY). Set domain and keywords in `config/default.yaml`.")
