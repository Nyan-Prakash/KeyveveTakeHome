"""Password hashing and verification using Argon2id."""

import argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, HashingError

from backend.app.config import get_settings


def get_password_hasher() -> PasswordHasher:
    """Get configured Argon2id password hasher.
    
    Returns:
        Configured PasswordHasher instance
    """
    return PasswordHasher(
        time_cost=3,        # 3 iterations (security vs performance balance)
        memory_cost=65536,  # 64 MB memory usage
        parallelism=1,      # Single thread (reduces complexity)
        hash_len=32,        # 32 byte hash output
        salt_len=16,        # 16 byte salt
        encoding="utf-8"    # UTF-8 encoding
    )


def hash_password(password: str) -> str:
    """Hash password using Argon2id.
    
    Args:
        password: Plain text password
        
    Returns:
        Argon2id hash string
        
    Raises:
        ValueError: If password is invalid
        HashingError: If hashing fails
    """
    settings = get_settings()
    
    # Validate password length
    if len(password) < settings.password_min_length:
        raise ValueError(f"Password must be at least {settings.password_min_length} characters")
    
    if len(password) > 128:  # Reasonable upper limit
        raise ValueError("Password must be 128 characters or less")
    
    try:
        ph = get_password_hasher()
        return ph.hash(password)
    except Exception as e:
        raise HashingError(f"Password hashing failed: {e}")


def verify_password(password: str, hash_string: str) -> bool:
    """Verify password against Argon2id hash.
    
    Args:
        password: Plain text password to verify
        hash_string: Stored Argon2id hash
        
    Returns:
        True if password matches hash, False otherwise
    """
    try:
        ph = get_password_hasher()
        ph.verify(hash_string, password)
        return True
    except VerifyMismatchError:
        return False
    except Exception:
        # Any other error (malformed hash, etc.) = invalid
        return False


def needs_rehash(hash_string: str) -> bool:
    """Check if password hash needs to be updated.
    
    This can happen if hash parameters change or Argon2 version updates.
    
    Args:
        hash_string: Stored Argon2id hash
        
    Returns:
        True if hash should be regenerated, False otherwise
    """
    try:
        ph = get_password_hasher()
        return ph.check_needs_rehash(hash_string)
    except Exception:
        # If we can't check, assume it needs rehash
        return True


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password.
    
    Used for temporary passwords, API keys, etc.
    
    Args:
        length: Password length (minimum 12)
        
    Returns:
        Secure random password string
    """
    import secrets
    import string
    
    if length < 12:
        raise ValueError("Generated password must be at least 12 characters")
    
    # Character set: letters, digits, safe symbols
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    
    # Generate password ensuring at least one of each character type
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase), 
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*")
    ]
    
    # Fill remaining length with random characters
    for _ in range(length - 4):
        password.append(secrets.choice(chars))
    
    # Shuffle to avoid predictable patterns
    secrets.SystemRandom().shuffle(password)
    
    return "".join(password)
