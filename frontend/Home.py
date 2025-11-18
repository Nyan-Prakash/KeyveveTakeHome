"""Home page for Keyveve Travel Planner."""

import streamlit as st
from auth import auth

st.set_page_config(
    page_title="Keyveve Travel Planner",
    page_icon="✈️",
    layout="wide",
)

# Restore session if possible
auth.restore_session_if_needed()

# Show authentication status in sidebar
auth.show_auth_sidebar()

st.title("✈️ Keyveve Travel Planner")
st.markdown("AI-powered travel planning with RAG-enhanced knowledge")

# Welcome message for authenticated users
if auth.is_authenticated:
    user = auth.current_user
    if user:
        st.success(f"🎉 Welcome back, **{user.get('email', 'User')}**!")
    else:
        st.success("🎉 Welcome back!")
else:
    st.info("👋 Welcome! Please log in or sign up to access all features.")

st.divider()

# Authentication Section
if not auth.is_authenticated:
    st.subheader("🔐 Get Started")
    st.markdown("Sign up or log in to access all features!")
    
    col_auth1, col_auth2, col_auth3 = st.columns([1, 1, 2])
    
    with col_auth1:
        if st.button("🔑 Login", key="home_login", use_container_width=True):
            st.switch_page("pages/00_Login.py")
    
    with col_auth2:
        if st.button("📝 Sign Up", key="home_signup", use_container_width=True):
            st.switch_page("pages/00_Signup.py")
    
    with col_auth3:
        st.markdown("*Create your account to save destinations and chat with AI*")
    
    st.divider()

# Navigation cards
if auth.is_authenticated:
    # Full access for authenticated users
    col1, col2, col3, col4 = st.columns(4)
else:
    # Limited preview for non-authenticated users
    st.info("🔒 **Login required** - The sections below require authentication")
    col1, col2, col3, col4 = st.columns(4)

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
    if auth.is_authenticated:
        if st.button("Go to Destinations", key="nav_dest", use_container_width=True):
            st.switch_page("pages/01_Destinations.py")
    else:
        if st.button("🔒 Login Required", key="nav_dest_locked", use_container_width=True, disabled=True):
            pass

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
    if auth.is_authenticated:
        if st.button("Go to Knowledge Base", key="nav_kb", use_container_width=True):
            st.switch_page("pages/02_Knowledge_Base.py")
    else:
        if st.button("🔒 Login Required", key="nav_kb_locked", use_container_width=True, disabled=True):
            pass

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
    if auth.is_authenticated:
        if st.button("Go to Plan", key="nav_plan", use_container_width=True):
            st.switch_page("pages/03_Plan.py")
    else:
        if st.button("🔒 Login Required", key="nav_plan_locked", use_container_width=True, disabled=True):
            pass

with col4:
    st.subheader("💬 Chat Plan")
    st.markdown(
        """
        Interactive AI assistant:
        - Chat about destinations
        - Get travel recommendations
        - Real-time planning help
        """
    )
    if auth.is_authenticated:
        if st.button("Go to Chat", key="nav_chat", use_container_width=True):
            st.switch_page("pages/04_Chat_Plan.py")
    else:
        if st.button("🔒 Login Required", key="nav_chat_locked", use_container_width=True, disabled=True):
            pass

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
