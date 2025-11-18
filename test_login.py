#!/usr/bin/env python3
"""Test user authentication directly."""

from backend.app.db.session import get_session_factory
from backend.app.db.models.user import User
from backend.app.security.passwords import verify_password
from backend.app.security.jwt import create_access_token, create_refresh_token


def test_login(email: str, password: str):
    """Test the login process step by step."""
    factory = get_session_factory()
    session = factory()
    
    try:
        print(f"1. Looking up user: {email}")
        user = session.query(User).filter(User.email == email).first()
        if not user:
            print("❌ User not found")
            return False
        print(f"✅ User found: {user.user_id}")
        
        print(f"2. Verifying password")
        if not verify_password(password, user.password_hash):
            print("❌ Password verification failed")
            return False
        print("✅ Password verified")
        
        print("3. Creating tokens")
        access_token = create_access_token(user.user_id, user.org_id)
        refresh_token = create_refresh_token(user.user_id, user.org_id)
        print(f"✅ Access token created: {len(access_token)} chars")
        print(f"✅ Refresh token created: {len(refresh_token)} chars")
        
        print("\n🎉 Login successful!")
        print(f"Access token: {access_token[:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Login failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    test_login("demo@keyveve.com", "password123")
