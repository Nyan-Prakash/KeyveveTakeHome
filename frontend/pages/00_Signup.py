"""Signup page for Triply Travel Planner."""

import streamlit as st
import re
from auth import auth

st.set_page_config(
    page_title="Sign Up - Triply Travel Planner",
    page_icon="📝",
    layout="centered",
)

# If already logged in, redirect to home
if auth.is_authenticated:
    st.success("You are already logged in!")
    if st.button("Go to Home"):
        st.switch_page("Home.py")
    st.stop()

st.title("📝 Create Your Account")
st.markdown("Join Triply and start planning amazing trips with AI!")

# Helper functions for validation
def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Password is strong"

# Signup form
with st.form("signup_form"):
    st.subheader("Account Information")
    
    email = st.text_input(
        "📧 Email Address", 
        placeholder="Enter your email address",
        type="default",
        help="We'll use this for login and important notifications"
    )
    
    password = st.text_input(
        "🔒 Password", 
        placeholder="Create a strong password",
        type="password",
        help="Minimum 8 characters with letters and numbers"
    )
    
    password_confirm = st.text_input(
        "🔒 Confirm Password", 
        placeholder="Re-enter your password",
        type="password"
    )
    
    # Terms agreement
    st.divider()
    agree_terms = st.checkbox(
        "I agree to the Terms of Service and Privacy Policy",
        help="By creating an account, you agree to our terms and conditions"
    )
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        signup_submitted = st.form_submit_button("📝 Create Account", use_container_width=True)
    
    with col2:
        if st.form_submit_button("🔑 Login Instead", use_container_width=True):
            st.switch_page("pages/00_Login.py")

# Handle signup
if signup_submitted:
    # Validation
    errors = []
    
    if not email:
        errors.append("Email is required")
    elif not validate_email(email):
        errors.append("Please enter a valid email address")
    
    if not password:
        errors.append("Password is required")
    else:
        is_valid, msg = validate_password(password)
        if not is_valid:
            errors.append(msg)
    
    if password != password_confirm:
        errors.append("Passwords do not match")
    
    if not agree_terms:
        errors.append("You must agree to the Terms of Service")
    
    # Show errors or proceed with signup
    if errors:
        st.error("Please fix the following errors:")
        for error in errors:
            st.error(f"• {error}")
    else:
        with st.spinner("Creating your account..."):
            if auth.signup(email, password):
                st.success("Account created successfully! Welcome to Triply!")
                st.balloons()
                # Small delay to show success message
                st.rerun()

st.divider()

# Benefits of signing up
st.markdown("""
### 🌟 Why Join Triply?

✈️ **AI-Powered Planning** - Get personalized travel recommendations  
🧠 **Knowledge Base** - Access curated travel information  
💬 **Chat Assistant** - Get instant answers about your destinations  
📍 **Destination Management** - Save and organize your favorite places  
🔒 **Secure & Private** - Your data is protected with enterprise-grade security
""")

# Navigation back to home
if st.button("🏠 Back to Home", use_container_width=True):
    st.switch_page("Home.py")
