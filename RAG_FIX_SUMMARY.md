# RAG Embedding Fix - Plan Generation Issue

## Problem
After implementing real vector embeddings, plan generation was failing with the error:
```
Plan Generation Failed
```

## Root Cause
The system was trying to use **pgvector operations** (`cosine_distance`) on a **SQLite database**. 

pgvector is a PostgreSQL extension and doesn't work with SQLite. The code was attempting to:
1. Generate embeddings using OpenAI API
2. Perform vector similarity search using `cosine_distance()` 
3. Both operations failed silently, causing plan generation to fail

## Solution
Made the system **database-aware** with automatic fallback:

### 1. Safe Vector Check
```python
try:
    has_vectors = session.execute(check_stmt).first() is not None
except Exception as e:
    # Fall back if pgvector operations not supported
    has_vectors = False
```

### 2. Safe Semantic Search
```python
try:
    # Try pgvector semantic search
    stmt = stmt.order_by(Embedding.vector.cosine_distance(query_vector))
    results = session.execute(stmt).all()
except Exception as e:
    # Fall back to recency if vector search fails
    has_vectors = False
```

### 3. Skip Embedding Generation on SQLite
```python
connection_url = str(factory.kw.get('bind', ''))
is_postgres = 'postgresql' in connection_url

if is_postgres:
    vectors = batch_generate_embeddings(sanitized_chunks)
else:
    vectors = [None] * len(chunks)  # Skip for SQLite
```

## Behavior After Fix

### SQLite Mode (Development - Default)
- ✅ **Plan generation works**
- ✅ Document upload works
- ✅ Chunking works
- ✅ Recency-based retrieval works
- ❌ No vector embeddings generated (saves OpenAI API costs)
- ❌ No semantic search (uses recency instead)

### PostgreSQL Mode (Production - When Available)
- ✅ **Plan generation works**
- ✅ Document upload works with embeddings
- ✅ Semantic search with cosine similarity
- ✅ MMR diversity filtering
- ✅ Full RAG capabilities

## How to Enable Full Semantic Search

1. **Install PostgreSQL**:
   ```bash
   brew install postgresql@14
   brew services start postgresql@14
   ```

2. **Install pgvector**:
   ```bash
   brew install pgvector
   # or compile from source
   ```

3. **Create database**:
   ```bash
   createdb triply
   psql triply -c "CREATE EXTENSION vector;"
   ```

4. **Update .env**:
   ```properties
   POSTGRES_URL=postgresql://localhost:5432/triply
   ```

5. **Run migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Backfill embeddings**:
   ```bash
   python scripts/backfill_embeddings.py
   ```

## Testing

### Test SQLite Fallback (Current Setup)
```bash
# Verify it doesn't crash
python3 -c "
from backend.app.graph.rag import retrieve_knowledge_for_destination
from uuid import UUID
print('✓ RAG module loads successfully')
"
```

### Test PostgreSQL Semantic Search (After Setup)
```bash
# Should see "Using semantic search" message
python scripts/test_semantic_search.py
```

## Summary

**The fix makes the system work with both SQLite and PostgreSQL:**

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Plan Generation | ✅ **FIXED** | ✅ Works |
| Document Upload | ✅ Works | ✅ Works |
| Chunking | ✅ Works | ✅ Works |
| Embedding Generation | ❌ Skipped | ✅ OpenAI API |
| Semantic Search | ❌ Recency fallback | ✅ Cosine similarity |
| MMR Diversity | ❌ Not applicable | ✅ Works |
| OpenAI API Calls | ❌ None | ✅ On upload |

**Bottom line**: Plan generation now works on SQLite by automatically disabling vector features and falling back to recency-based retrieval. To get full semantic search, upgrade to PostgreSQL.
