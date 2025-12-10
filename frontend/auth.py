"""Authentication utilities for Streamlit frontend."""

import streamlit as st
import requests
from typing import Optional, Dict, Any
import json
import streamlit.components.v1 as components


class AuthManager:
    """Manages user authentication state in Streamlit."""
    
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url
        self._ensure_session_initialized()
        
    def _ensure_session_initialized(self):
        """Ensure session state has the required keys initialized."""
        if "access_token" not in st.session_state:
            st.session_state.access_token = None
        if "refresh_token" not in st.session_state:
            st.session_state.refresh_token = None  
        if "current_user" not in st.session_state:
            st.session_state.current_user = None
        if "auth_checked" not in st.session_state:
            st.session_state.auth_checked = False
            st.session_state.auth_checked = False
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated."""
        return "access_token" in st.session_state and st.session_state.access_token is not None
    
    @property 
    def current_user(self) -> Optional[Dict[str, Any]]:
        """Get current user information."""
        return st.session_state.get("current_user")
        
    def restore_session_if_needed(self):
        """Attempt to restore session by checking stored tokens."""
        # Ensure session is initialized first
        self._ensure_session_initialized()
        
        # If we don't have a token but haven't checked for stored ones yet
        if not self.is_authenticated and not st.session_state.auth_checked:
            st.session_state.auth_checked = True
            
            # Try to load token from browser storage
            stored_token = self._load_token_from_storage()
            if stored_token:
                st.session_state.access_token = stored_token
                self._fetch_user_info()
                if self.is_authenticated:
                    st.rerun()
        
        # If we have a token but no user info, try to fetch it
        elif self.is_authenticated and not st.session_state.current_user:
            self._fetch_user_info()
    
    def signup(self, email: str, password: str) -> bool:
        """Sign up a new user."""
        try:
            response = requests.post(
                f"{self.backend_url}/auth/signup",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self._save_tokens(data)
                self._fetch_user_info()
                st.success(f"Welcome! Account created for {email}")
                return True
            else:
                error_msg = response.json().get("detail", "Signup failed")
                st.error(f"Signup failed: {error_msg}")
                return False
                
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")
            return False
        except Exception as e:
            st.error(f"Signup error: {e}")
            return False
    
    def login(self, email: str, password: str) -> bool:
        """Log in an existing user."""
        try:
            response = requests.post(
                f"{self.backend_url}/auth/login",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self._save_tokens(data)
                self._fetch_user_info()
                st.success(f"Welcome back, {email}!")
                return True
            else:
                error_msg = response.json().get("detail", "Login failed")
                st.error(f"Login failed: {error_msg}")
                return False
                
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")
            return False
        except Exception as e:
            st.error(f"Login error: {e}")
            return False
    
    def logout(self):
        """Log out the current user."""
        try:
            # Call logout endpoint if token exists
            if "access_token" in st.session_state:
                requests.post(
                    f"{self.backend_url}/auth/logout",
                    headers=self.get_auth_headers()
                )
        except:
            pass  # Ignore errors on logout
        
        # Clear session state and browser storage
        self._clear_auth_state()
        self._clear_token_from_storage()
        st.success("Logged out successfully!")
        st.rerun()
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests."""
        if not self.is_authenticated:
            return {}
        
        # Check if token exists 
        token = st.session_state.get("access_token")
        if not token:
            return {}
        
        # Return headers with the current token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def validate_current_session(self) -> bool:
        """Explicitly validate the current session - use sparingly."""
        return self._validate_token()
    
    def _validate_token(self) -> bool:
        """Validate current access token by making a test request."""
        try:
            token = st.session_state.get("access_token")
            if not token:
                return False
                
            # Test token with a simple endpoint
            response = requests.get(
                f"{self.backend_url}/auth/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                # Update user info while we're here
                st.session_state.current_user = response.json()
                return True
            else:
                self._clear_auth_state()
                return False
                
        except Exception as e:
            self._clear_auth_state()
            return False
    
    def _save_tokens(self, data: Dict[str, Any]):
        """Save authentication tokens to session state and browser storage."""
        st.session_state.access_token = data.get("access_token")
        st.session_state.refresh_token = data.get("refresh_token")
        
        # Save to browser storage for persistence
        token = st.session_state.access_token
        if token:
            self._save_token_to_storage(token)
            print(f"✅ Token saved: {token[:50]}...")
        else:
            print("❌ No token in response")
    
    def _fetch_user_info(self):
        """Fetch and save current user information."""
        try:
            headers = self.get_auth_headers()
            if not headers.get("Authorization"):
                return
                
            response = requests.get(
                f"{self.backend_url}/auth/me",
                headers=headers
            )
            
            if response.status_code == 200:
                user_data = response.json()
                st.session_state.current_user = user_data
            else:
                # Token might be invalid, clear auth state
                self._clear_auth_state()
                
        except Exception as e:
            # If we can't fetch user info, clear auth state
            self._clear_auth_state()
    
    def _clear_auth_state(self):
        """Clear authentication state without showing success message."""
        keys_to_clear = ["access_token", "refresh_token", "current_user", "auth_checked"]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    def require_auth(self):
        """Decorator/function to require authentication for a page."""
        # First try to restore session
        self.restore_session_if_needed()
        
        if not self.is_authenticated:
            st.warning("🔐 Please log in to access this page")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔑 Go to Login", use_container_width=True):
                    st.switch_page("pages/00_Login.py")
            with col2:
                if st.button("📝 Go to Sign Up", use_container_width=True):
                    st.switch_page("pages/00_Signup.py")
            st.stop()
    
    def show_auth_sidebar(self):
        """Show authentication status and controls in sidebar."""
        with st.sidebar:
            st.divider()
            
            if self.is_authenticated:
                user = self.current_user
                if user:
                    st.success(f"👋 Welcome, {user.get('email', 'User')}!")
                    st.write(f"**User ID:** {user.get('user_id', 'Unknown')}")
                    st.write(f"**Org ID:** {user.get('org_id', 'Unknown')}")
                else:
                    st.success("👋 Welcome! You are logged in.")
                
                # Logout button
                st.divider()
                if st.button("🚪 Logout", use_container_width=True, type="secondary", key="sidebar_logout_btn"):
                    self.logout()
            else:
                st.warning("🔐 Not logged in")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔑 Login", use_container_width=True, key="sidebar_login_btn"):
                        st.switch_page("pages/00_Login.py")
                with col2:
                    if st.button("� Sign Up", use_container_width=True, key="sidebar_signup_btn"):
                        st.switch_page("pages/00_Signup.py")
                        
    def show_logout_button(self, key: str = "logout_main"):
        """Show a standalone logout button."""
        if self.is_authenticated:
            if st.button("🚪 Logout", key=key, type="secondary"):
                self.logout()
    
    def _save_token_to_storage(self, token: str):
        """Save token to browser storage using a simple component."""
        if token:
            components.html(f"""
            <script>
                localStorage.setItem('triply_auth_token', '{token}');
                sessionStorage.setItem('triply_auth_token', '{token}');
            </script>
            """, height=0)
            
    def _load_token_from_storage(self):
        """Load token from browser storage."""
        result = components.html("""
        <script>
            const token = localStorage.getItem('triply_auth_token') || sessionStorage.getItem('triply_auth_token');
            if (token) {
                // Return the token to Streamlit
                const returnData = {token: token};
                if (window.streamlitSetComponentValue) {
                    window.streamlitSetComponentValue(returnData);
                }
            }
        </script>
        """, height=0)
        
        if result and isinstance(result, dict) and 'token' in result:
            return result['token']
        return None
        
    def _clear_token_from_storage(self):
        """Clear token from browser storage."""
        components.html("""
        <script>
            localStorage.removeItem('triply_auth_token');
            sessionStorage.removeItem('triply_auth_token');
        </script>
        """, height=0)


# Global auth manager instance
auth = AuthManager()
