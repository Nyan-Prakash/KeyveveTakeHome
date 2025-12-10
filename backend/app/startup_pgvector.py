"""Enable pgvector extension on application startup."""

import logging
from sqlalchemy import text

from backend.app.db.session import get_session_factory

logger = logging.getLogger(__name__)


def enable_pgvector_on_startup() -> bool:
    """
    Enable pgvector extension in PostgreSQL on application startup.
    
    Returns:
        True if pgvector is available, False otherwise
    """
    try:
        factory = get_session_factory()
        session = factory()
        
        try:
            # Check if we're using PostgreSQL
            result = session.execute(text("SELECT version()"))
            version = result.scalar()
            
            if "PostgreSQL" not in version:
                logger.info("Not using PostgreSQL, pgvector not needed")
                return False
            
            # Try to create the extension (idempotent - won't fail if exists)
            logger.info("Attempting to enable pgvector extension...")
            session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            session.commit()
            
            # Verify it's enabled
            result = session.execute(text(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            ))
            is_enabled = result.scalar()
            
            if is_enabled:
                logger.info("✅ pgvector extension is enabled and ready")
                return True
            else:
                logger.warning("⚠️ pgvector extension could not be enabled")
                return False
                
        finally:
            session.close()
            
    except Exception as e:
        logger.warning(f"⚠️ Could not enable pgvector: {str(e)[:100]}")
        logger.info("Application will use Python-based similarity fallback")
        return False
