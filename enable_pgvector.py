"""Script to enable pgvector extension on Railway PostgreSQL.

Run this script once after deploying to Railway to enable pgvector support.
"""

import os
import sys
from sqlalchemy import create_engine, text

def enable_pgvector():
    """Enable pgvector extension in the database."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("   Make sure you're running this on Railway or set DATABASE_URL locally")
        sys.exit(1)
    
    print(f"🔌 Connecting to database...")
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check if pgvector is already installed
            result = conn.execute(text(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            ))
            already_installed = result.scalar()
            
            if already_installed:
                print("✅ pgvector extension is already enabled!")
            else:
                print("📦 Enabling pgvector extension...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                print("✅ pgvector extension enabled successfully!")
            
            # Verify installation
            result = conn.execute(text(
                "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"
            ))
            row = result.fetchone()
            
            if row:
                print(f"✅ Verification: pgvector version {row[1]} is installed")
                print("\n🎉 Success! Your application can now use native pgvector for fast similarity search.")
                print("   Redeploy your application or restart it to take effect.")
            else:
                print("⚠️  Warning: Extension creation succeeded but verification failed")
                print("   This might mean pgvector is not available in your PostgreSQL installation")
                
    except Exception as e:
        print(f"❌ Error enabling pgvector: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure your PostgreSQL version supports pgvector (14+)")
        print("2. Railway's PostgreSQL should have pgvector pre-installed")
        print("3. If not, contact Railway support or use the Python fallback")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("Railway pgvector Extension Enabler")
    print("=" * 60)
    print()
    enable_pgvector()
