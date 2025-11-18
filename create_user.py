#!/usr/bin/env python3
"""Create a test user with proper password hashing."""

import sys
from datetime import datetime, timezone
from uuid import uuid4

from backend.app.db.models.org import Org
from backend.app.db.models.user import User
from backend.app.db.session import get_session_factory
from backend.app.security.passwords import hash_password


def create_user(email: str, password: str):
    """Create a user with proper password hashing."""
    factory = get_session_factory()
    session = factory()
    
    try:
        # Check if user already exists
        existing_user = session.query(User).filter_by(email=email).first()
        if existing_user:
            print(f"❌ User {email} already exists")
            return existing_user
            
        # Get or create default org
        org = session.query(Org).first()
        if not org:
            org = Org(
                org_id=uuid4(),
                name="Default Organization",
                created_at=datetime.now(timezone.utc)
            )
            session.add(org)
            session.flush()
            print(f"✅ Created organization: {org.name}")
        
        # Hash the password properly
        password_hash = hash_password(password)
        
        # Create user
        user = User(
            user_id=uuid4(),
            org_id=org.org_id,
            email=email,
            password_hash=password_hash,
            created_at=datetime.now(timezone.utc)
        )
        
        session.add(user)
        session.commit()
        
        print(f"✅ Created user: {email}")
        print(f"   User ID: {user.user_id}")
        print(f"   Org ID: {user.org_id}")
        print(f"   Password: {password}")
        
        return user
        
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        session.rollback()
        return None
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python create_user.py <email> <password>")
        print("Example: python create_user.py test@example.com mypassword123")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    create_user(email, password)
