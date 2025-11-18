#!/bin/bash

# Generate RSA key pair for JWT token signing

set -e

echo "🔑 Generating RSA key pair for JWT..."

# Generate private key (2048-bit RSA)
openssl genrsa -out jwt-private.pem 2048

# Generate public key from private key
openssl rsa -in jwt-private.pem -pubout -out jwt-public.pem

echo "✅ JWT keys generated successfully:"
echo "  - Private key: jwt-private.pem"  
echo "  - Public key: jwt-public.pem"
echo ""
echo "🔐 Security note: Keep the private key secure and never commit to version control!"
echo ""
echo "📝 Add these to your .env file:"
echo ""

# Format for .env file (escape newlines)
echo "JWT_PRIVATE_KEY_PEM=\"$(cat jwt-private.pem | tr '\n' '\\n')\""
echo ""
echo "JWT_PUBLIC_KEY_PEM=\"$(cat jwt-public.pem | tr '\n' '\\n')\""
echo ""

# Clean up generated files (optional - user can decide)
echo "💡 Generated files jwt-private.pem and jwt-public.pem can be deleted after adding to .env"
echo "   Run: rm jwt-private.pem jwt-public.pem"
