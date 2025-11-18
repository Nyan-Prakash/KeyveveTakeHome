"""Login page for Keyveve Travel Planner."""

import streamlit as st
from auth import auth

st.set_page_config(
    page_title="Login - Keyveve Travel Planner",
    page_icon="🔑",
    layout="centered",
)

# If already logged in, redirect to home
if auth.is_authenticated:
    st.success("You are already logged in!")
    if st.button("Go to Home"):
        st.switch_page("Home.py")
    st.stop()

st.title("🔑 Login to Keyveve")
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
                st.success("Login successful! Redirecting...")
                st.balloons()
                # Small delay to show success message
                st.rerun()

st.divider()

# Demo credentials
st.info("""
💡 **Demo Credentials:**
- Email: `demo@keyveve.com`  
- Password: `password123`

Or create a new account with the Sign Up button above.
""")

# Navigation back to home
if st.button("🏠 Back to Home", use_container_width=True):
    st.switch_page("Home.py")
