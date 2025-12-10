"""Login page for Triply Travel Planner."""

import streamlit as st
import time
from auth import auth

st.set_page_config(
    page_title="Login - Triply Travel Planner",
    page_icon="🔑",
    layout="centered",
)

# If already logged in, show navigation options
if auth.is_authenticated:
    st.success("You are already logged in!")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💬 Go to Chat Plan", use_container_width=True, type="primary"):
            st.switch_page("pages/04_Chat_Plan.py")
    with col2:
        if st.button("🏠 Go to Home", use_container_width=True):
            st.switch_page("Home.py")
    st.stop()

st.title("🔑 Login to Triply")
st.markdown("Welcome back! Please sign in to your account.")

# Login form
with st.form("login_form"):
    email = st.text_input(
        "📧 Email", 
        placeholder="Enter your email address",
        type="default"
    )
    
    password = st.text_input(
        "🔒 Password", 
        placeholder="Enter your password",
        type="password"
    )
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        login_submitted = st.form_submit_button("🔑 Login", use_container_width=True)
    
    with col2:
        if st.form_submit_button("📝 Sign Up Instead", use_container_width=True):
            st.switch_page("pages/00_Signup.py")

# Handle login
if login_submitted:
    if not email or not password:
        st.error("Please enter both email and password")
    else:
        with st.spinner("Logging in..."):
            if auth.login(email, password):
                st.success("Login successful! 🎉")
                st.balloons()
                
                # Show quick navigation options after successful login
                st.markdown("**Where would you like to go?**")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💬 Start Planning (Chat)", use_container_width=True, type="primary", key="goto_chat"):
                        st.switch_page("pages/04_Chat_Plan.py")
                with col2:
                    if st.button("🏠 Go to Home", use_container_width=True, key="goto_home"):
                        st.switch_page("Home.py")
                
                # Auto-redirect after 3 seconds if no action
                with st.empty():
                    for i in range(3, 0, -1):
                        st.info(f"Auto-redirecting to Chat Plan in {i} seconds... (or click a button above)")
                        time.sleep(1)
                    st.switch_page("pages/04_Chat_Plan.py")

st.divider()

# Demo credentials
st.info("""
💡 **Demo Credentials:**
- Email: `demo@triply.com`  
- Password: `password123`

Or create a new account with the Sign Up button above.
""")

# Navigation back to home
col1, col2 = st.columns(2)
with col1:
    if st.button("🏠 Back to Home", use_container_width=True):
        st.switch_page("Home.py")
with col2:
    if st.button("💬 Go to Chat Plan", use_container_width=True, type="secondary"):
        st.switch_page("pages/04_Chat_Plan.py")
