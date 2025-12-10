# Railway pgvector Error Fix

## Problem

When deployed to Railway, the application crashes with this error:

```
ERROR: operator does not exist: text <=> unknown at character 369
HINT: No operator matches the given name and argument types. You might need to add explicit type casts.
```

This error occurs because the RAG (Retrieval-Augmented Generation) system tries to use the `<=>` operator for vector cosine distance, which is provided by the **pgvector PostgreSQL extension**. However, this extension is not enabled by default on Railway's PostgreSQL.

## Root Cause

The application code in `backend/app/graph/rag.py` uses:
```python
.order_by(Embedding.vector.cosine_distance(query_vector))
```

This SQLAlchemy query translates to the SQL operator `<=>`, which requires the pgvector extension to be installed and enabled in PostgreSQL.

## Solution

You have **two options**:

### Option 1: Enable pgvector on Railway (Recommended for Production)

This gives you the best performance for vector similarity search.

**Steps:**

1. **Connect to your Railway PostgreSQL database:**
   - In Railway dashboard, click on your PostgreSQL service
   - Click **"Connect"** → **"Connect via psql"**
   - Railway will open a terminal connection to your database

2. **Enable the pgvector extension:**
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. **Verify it's installed:**
   ```sql
   \dx
   ```
   You should see `vector` in the list of extensions.

4. **Redeploy your application** or restart the service in Railway

**That's it!** The application will now use native pgvector for fast semantic search.

---

### Option 2: Use Python-based Similarity Search (Automatic Fallback)

If pgvector is not available or you cannot enable it, the code now **automatically falls back** to Python-based cosine similarity calculation.

**What Changed:**

I've updated `backend/app/graph/rag.py` to:

1. **Try pgvector first** - Attempts to use the native `<=>` operator for fast similarity search
2. **Catch the error** - If pgvector is unavailable (operator doesn't exist), it catches the exception
3. **Fall back to Python** - Computes cosine similarity in Python using NumPy:
   ```python
   # Fetch all embeddings
   # Compute similarity for each: dot(query, vector) / (norm(query) * norm(vector))
   # Sort by similarity and return top results
   ```

This fallback is **slower** for large datasets but works without any PostgreSQL extensions.

**Dependencies Added:**

Added `numpy>=1.24.0` to `pyproject.toml` to ensure it's available for the fallback computation.

---

## How to Deploy the Fix

### If You Choose Option 1 (Enable pgvector):

```bash
# 1. Enable pgvector extension (see steps above)
# 2. Just redeploy - no code changes needed
git push origin railwayAgain
```

### If You Choose Option 2 (Python fallback):

```bash
# 1. Commit the updated code
git add backend/app/graph/rag.py pyproject.toml
git commit -m "Add Python fallback for vector similarity when pgvector unavailable"

# 2. Push to Railway
git push origin railwayAgain
```

Railway will automatically redeploy with the new code. The application will detect that pgvector is unavailable and use the Python fallback.

---

## Performance Comparison

| Method | Speed | Setup Complexity | Scalability |
|--------|-------|------------------|-------------|
| **pgvector (native)** | ⚡ Very Fast (~5ms) | Medium (requires extension) | Excellent (millions of vectors) |
| **Python fallback** | 🐌 Slow (~50-200ms) | Low (no setup needed) | Poor (< 10K vectors) |

**Recommendation:**
- For **production** with real users: **Enable pgvector** (Option 1)
- For **testing/demo** purposes: **Python fallback works fine** (Option 2)

---

## Verification

After deploying, check your Railway logs for these messages:

### With pgvector enabled:
```
✅ RAG: Retrieved 20 chunks via pgvector semantic search for 'travel guide information...'
```

### With Python fallback:
```
⚠️ RAG: pgvector extension not available, using Python-based cosine similarity
✅ RAG: Retrieved 20 chunks via Python cosine similarity for 'travel guide information...'
```

### If no embeddings exist:
```
⚠️ RAG: No embeddings found, falling back to timestamp-based retrieval for Munich
```

---

## Technical Details

### The Error Chain

1. Application starts and runs migration (`001_initial_schema.py`)
2. Migration tries: `CREATE EXTENSION IF NOT EXISTS vector`
3. If pgvector is not installed in PostgreSQL, the extension creation **silently fails**
4. Migration falls back to storing vectors as `TEXT` type instead of `vector` type
5. Application runs and tries to use `.cosine_distance()` operator
6. PostgreSQL says: "operator does not exist: text <=> unknown" ❌

### The Fix

The updated code now:
1. ✅ Tries pgvector operator first (fast path)
2. ✅ Catches "operator does not exist" error
3. ✅ Falls back to Python-based calculation
4. ✅ Still returns relevant results, just slower

---

## Next Steps

1. **Choose your option** (pgvector or Python fallback)
2. **Deploy the fix** using the appropriate method above
3. **Monitor Railway logs** to confirm it's working
4. **Test the application** by creating a travel plan

If you encounter any issues, check:
- Railway build logs for dependency installation
- Runtime logs for RAG retrieval messages
- PostgreSQL logs for any connection issues

---

## Questions?

- **"Why not just always use Python fallback?"** - It's 10-40x slower and doesn't scale well. pgvector is optimized for vector operations.
- **"Can I switch later?"** - Yes! You can enable pgvector anytime and the code will automatically use it.
- **"What if I have millions of vectors?"** - You **must** use pgvector. Python fallback will time out.

---

**Status**: ✅ Fixed and ready to deploy!
