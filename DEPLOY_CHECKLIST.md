# 🚀 Deploy to Railway - Complete Fix

## ⚠️ IMPORTANT: You MUST Enable pgvector

The Python fallback didn't work because Railway needs pgvector extension enabled. **This is a ONE-TIME setup step.**

## Step 1: Deploy the Updated Code

### 1.1 Commit the changes
```bash
git add backend/app/graph/rag.py pyproject.toml enable_pgvector.py test_rag_fallback.py RAILWAY_PGVECTOR_FIX.md DEPLOY_CHECKLIST.md
git commit -m "Fix pgvector detection and add enabler script"
```

### 1.2 Push to Railway
```bash
git push origin railwayAgain
```

### 1.3 Wait for deployment
- Railway will automatically build and deploy (2-3 minutes)

---

## Step 2: Enable pgvector Extension (REQUIRED)

### Option A: Run the Script (Easiest)

After deployment, run this command in Railway's terminal:

1. Go to Railway dashboard → Your service → "Shell" tab
2. Run:
```bash
python enable_pgvector.py
```

You should see:
```
✅ pgvector extension enabled successfully!
✅ Verification: pgvector version 0.5.1 is installed
```

### Option B: Manual SQL (Alternative)

1. Railway dashboard → PostgreSQL service → Connect → psql
2. Run this SQL:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
\dx  -- verify it's installed
```

You should see `vector` in the list.

---

## Step 3: Restart Your Application

After enabling pgvector:

1. Railway dashboard → Your backend service
2. Click "Restart" or redeploy

---

## Step 4: Verify It Works

Check Railway logs for:
```
✅ RAG: Retrieved 20 chunks via pgvector semantic search
```

If you see this, pgvector is working! 🎉

---

## Why This is Required

- Railway's PostgreSQL **has pgvector installed** but **not enabled by default**
- The `<=>` operator error means the extension exists but isn't activated
- You must run `CREATE EXTENSION vector` once to enable it
- After that, it works forever (persists across deploys)

---

## Troubleshooting

### Error: "operator does not exist: text <=> unknown"
**Status**: pgvector not enabled yet
**Fix**: Run Step 2 above to enable it

### Error: "extension "vector" does not exist"
**Status**: pgvector not installed in PostgreSQL
**Fix**: Contact Railway support OR use SQLite locally

### Success: "Retrieved X chunks via pgvector"
**Status**: ✅ Working correctly!
**Action**: Nothing needed - enjoy your app!

---

## Alternative: Use SQLite Locally

If you're developing locally and don't want to deal with PostgreSQL:

```bash
# Use SQLite instead
export DATABASE_URL="sqlite:///./keyveve.db"
python -m alembic upgrade head
python seed_db.py
```

SQLite doesn't support pgvector, so it will use the timestamp fallback (works fine for dev).

---

## Quick Reference

| Step | Command | Where |
|------|---------|-------|
| 1. Deploy | `git push origin railwayAgain` | Local |
| 2. Enable pgvector | `python enable_pgvector.py` | Railway Shell |
| 3. Restart | Click "Restart" | Railway Dashboard |
| 4. Verify | Check logs | Railway Logs |

---

**Ready?** Start with Step 1 above! 🚀
