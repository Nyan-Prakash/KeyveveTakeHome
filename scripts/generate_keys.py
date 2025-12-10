#!/usr/bin/env python3
"""
Generate RSA key pairs for JWT authentication.

This script generates a 4096-bit RSA key pair and outputs them in PEM format
suitable for use with the Triply Travel Planner application.

Usage:
    python scripts/generate_keys.py
    
The output can be copied directly into your .env file or Railway/Render configuration.
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def generate_rsa_keypair(key_size: int = 4096):
    """
    Generate an RSA key pair.
    
    Args:
        key_size: Size of the RSA key in bits (default: 4096)
        
    Returns:
        tuple: (private_key, public_key) as PEM-encoded strings
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    # Serialize private key to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # Get public key
    public_key = private_key.public_key()
    
    # Serialize public key to PEM format
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return private_pem, public_pem


def main():
    """Generate and print RSA key pairs."""
    print("=" * 80)
    print("Generating RSA Key Pair for JWT Authentication")
    print("=" * 80)
    print()
    print("Generating 4096-bit RSA keys (this may take a moment)...")
    print()
    
    private_key, public_key = generate_rsa_keypair()
    
    print("✓ Keys generated successfully!")
    print()
    print("=" * 80)
    print("PRIVATE KEY (Keep this secret!)")
    print("=" * 80)
    print()
    print('JWT_PRIVATE_KEY_PEM="', end='')
    # Print with escaped newlines for easy copying
    print(private_key.replace('\n', '\\n'), end='')
    print('"')
    print()
    
    print("=" * 80)
    print("PUBLIC KEY")
    print("=" * 80)
    print()
    print('JWT_PUBLIC_KEY_PEM="', end='')
    # Print with escaped newlines for easy copying
    print(public_key.replace('\n', '\\n'), end='')
    print('"')
    print()
    
    print("=" * 80)
    print("For Railway/Render (Multi-line format):")
    print("=" * 80)
    print()
    print("JWT_PRIVATE_KEY_PEM=")
    print(private_key)
    print()
    print("JWT_PUBLIC_KEY_PEM=")
    print(public_key)
    print()
    
    print("=" * 80)
    print("INSTRUCTIONS")
    print("=" * 80)
    print()
    print("1. Copy the keys above into your .env file")
    print("2. For Railway/Render: Use the multi-line format")
    print("3. For local .env: Use the escaped format (with \\n)")
    print("4. NEVER commit these keys to git!")
    print("5. NEVER share your private key!")
    print()
    print("⚠️  WARNING: Keep your private key secret and secure!")
    print()


if __name__ == "__main__":
    try:
        main()
    except ImportError:
        print()
        print("❌ Error: cryptography package not installed")
        print()
        print("Install it with:")
        print("  pip install cryptography")
        print()
        print("Or install all dependencies:")
        print("  pip install -e .")
        print()
