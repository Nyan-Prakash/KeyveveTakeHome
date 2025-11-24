#!/usr/bin/env python3
"""Test user authentication directly."""

from backend.app.db.models.user import User
from backend.app.security.passwords import hash_password, verify_password
from backend.app.security.jwt import create_access_token, create_refresh_token, verify_access_token


def test_login(test_session, test_user):
    """Test the login process step by step."""
    # Test user should exist (created by fixture)
    user = test_session.query(User).filter(User.email == test_user.email).first()
    assert user is not None, "User should exist"
    assert user.user_id == test_user.user_id
    
    # Test password verification
    # The test_user has password "testpassword123"
    assert verify_password("testpassword123", user.password_hash), "Password should verify"
    assert not verify_password("wrongpassword", user.password_hash), "Wrong password should fail"
    
    # Test token creation
    access_token = create_access_token(user.user_id, user.org_id)
    refresh_token = create_refresh_token(user.user_id, user.org_id)
    
    assert len(access_token) > 0, "Access token should be created"
    assert len(refresh_token) > 0, "Refresh token should be created"
    
    # Test token verification
    payload = verify_access_token(access_token)
    assert payload.user_id == user.user_id, "Token should contain correct user_id"
    assert payload.org_id == user.org_id, "Token should contain correct org_id"
