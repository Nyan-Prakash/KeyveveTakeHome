#!/bin/bash
# Setup script for PostgreSQL with pgvector

set -e

echo "🚀 Setting up PostgreSQL with pgvector for Keyveve"
echo "=================================================="

# Use local PostgreSQL without pgvector extension for now
# We'll use pure Python cosine similarity instead

# Create database if it doesn't exist
psql postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'keyveve'" | grep -q 1 || psql postgres -c "CREATE DATABASE keyveve;"

echo "✓ Database 'keyveve' ready"

# Update .env file
ENV_FILE=".env"
BACKUP_FILE=".env.backup"

# Backup existing .env
cp "$ENV_FILE" "$BACKUP_FILE"
echo "✓ Backed up .env to .env.backup"

# Update POSTGRES_URL
if grep -q "^POSTGRES_URL=" "$ENV_FILE"; then
    # Replace existing line
    sed -i '' 's|^POSTGRES_URL=.*|POSTGRES_URL=postgresql://localhost:5432/keyveve|' "$ENV_FILE"
else
    # Add new line
    echo "POSTGRES_URL=postgresql://localhost:5432/keyveve" >> "$ENV_FILE"
fi

echo "✓ Updated .env with PostgreSQL connection"

echo ""
echo "=================================================="
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Run migrations: alembic upgrade head"
echo "2. Test connection: python -c 'from backend.app.db.session import get_session_factory; print(\"✓ Connected\")'"
echo "3. Backfill embeddings: python scripts/backfill_embeddings.py"
echo ""
echo "Note: Using Python-based cosine similarity instead of pgvector extension"
echo "This works fine for development and small-to-medium datasets."
echo "=================================================="
