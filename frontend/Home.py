"""Home page for Keyveve Travel Planner."""

import streamlit as st

st.set_page_config(
    page_title="Keyveve Travel Planner",
    page_icon="✈️",
    layout="wide",
)

st.title("✈️ Keyveve Travel Planner")
st.markdown("AI-powered travel planning with RAG-enhanced knowledge")

st.divider()

# Navigation cards
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📍 Destinations")
    st.markdown(
        """
        Manage your travel destinations:
        - Create and edit destinations
        - View planning history
        - Track last run costs
        """
    )
    if st.button("Go to Destinations", key="nav_dest", use_container_width=True):
        st.switch_page("pages/01_Destinations.py")

with col2:
    st.subheader("📚 Knowledge Base")
    st.markdown(
        """
        Upload local knowledge:
        - Upload PDF/MD guides
        - View document chunks
        - RAG-enhanced planning
        """
    )
    if st.button("Go to Knowledge Base", key="nav_kb", use_container_width=True):
        st.switch_page("pages/02_Knowledge_Base.py")

with col3:
    st.subheader("🗓️ Plan")
    st.markdown(
        """
        Create and refine itineraries:
        - Generate AI plans
        - Apply what-if changes
        - View citations & decisions
        """
    )
    if st.button("Go to Plan", key="nav_plan", use_container_width=True):
        st.switch_page("pages/03_Plan.py")

st.divider()

# Feature highlights
st.subheader("🌟 Features")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown(
        """
        **Agentic Planning:**
        - Multi-constraint optimization
        - Automated repair loops
        - Deterministic selector
        - Real-time streaming progress

        **Knowledge Integration:**
        - Upload local guides (PDF/MD)
        - Automatic chunking & embedding
        - RAG retrieval with citations
        - PII-stripped embeddings
        """
    )

with col_b:
    st.markdown(
        """
        **What-If Flows:**
        - Adjust budget dynamically
        - Shift travel dates
        - Modify preferences
        - Compare iterations

        **System Transparency:**
        - Tool usage metrics
        - Node timing breakdown
        - Constraint violation tracking
        - Provenance citations
        """
    )

st.divider()

st.caption("PR11 — Streamlit Pages + RAG UX + What-If Flows | Keyveve Take-Home")
