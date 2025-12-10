# 🚂 Railway Deployment - Quick Reference

## Service Configuration

Your project has **3 services** that need to be deployed:

### 1. Backend Service

**Build Settings:**
- Dockerfile Path: `./backend/Dockerfile`
- Root Directory: `/`
- Start Command: `alembic upgrade head && uvicorn backend.app.main:create_app --host 0.0.0.0 --port $PORT --factory`

**Environment Variables:**
```bash
POSTGRES_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
OPENAI_API_KEY=sk-your-key-here
WEATHER_API_KEY=your-key-here
JWT_PRIVATE_KEY_PEM=<your-jwt-private-key>
JWT_PUBLIC_KEY_PEM=<your-jwt-public-key>
MCP_WEATHER_ENDPOINT=http://${{mcp-weather.RAILWAY_PRIVATE_DOMAIN}}:3001
UI_ORIGIN=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}
MCP_ENABLED=true
ENABLE_PDF_OCR=true
OCR_DPI_SCALE=2.0
```

### 2. Frontend Service

**Build Settings:**
- Dockerfile Path: `./frontend/Dockerfile`
- Root Directory: `/`
- Start Command: `streamlit run Home.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`

**Environment Variables:**
```bash
BACKEND_URL=http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000
```

**Networking:**
- ✅ Generate Public Domain (this is your app URL!)

### 3. MCP Weather Service

**Build Settings:**
- Dockerfile Path: `./mcp-server/Dockerfile`
- Root Directory: `/`
- Start Command: `node server.js`

**Environment Variables:**
```bash
WEATHER_API_KEY=your-key-here
PORT=3001
```

### 4. PostgreSQL Database

**Setup:**
- Click "+ New" → Database → PostgreSQL
- Name: `postgres`
- Railway auto-provisions this

### 5. Redis Database

**Setup:**
- Click "+ New" → Database → Redis
- Name: `redis`
- Railway auto-provisions this

---

## Common Issues & Fixes

### ❌ "Dockerfile does not exist"

**Problem:** Railway can't find your Dockerfile

**Solution:**
1. Go to service → Settings → Build
2. Set "Dockerfile Path" correctly:
   - Backend: `./backend/Dockerfile`
   - Frontend: `./frontend/Dockerfile`
   - MCP: `./mcp-server/Dockerfile`
3. Root Directory: `/` or blank
4. Redeploy

### ❌ Backend build fails

**Check:**
- All environment variables are set
- JWT keys include BEGIN/END markers
- Database URLs use Railway references: `${{Postgres.DATABASE_URL}}`

### ❌ Frontend can't reach backend

**Fix:**
- Set `BACKEND_URL` to: `http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000`
- Make sure backend is deployed and healthy first

### ❌ CORS errors

**Fix:**
- Set backend's `UI_ORIGIN` to: `https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}`
- Make sure frontend has a public domain generated

---

## Deployment Order

Deploy in this order to avoid dependency issues:

1. ✅ PostgreSQL database
2. ✅ Redis database
3. ✅ MCP Weather service
4. ✅ Backend service
5. ✅ Frontend service

Then run migrations:
```bash
railway run alembic upgrade head
railway run python seed_db.py
```

---

## Railway CLI Commands

```bash
# Install CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Run migrations
railway run alembic upgrade head
railway run python seed_db.py

# View logs
railway logs

# Check status
railway status

# SSH into service (for debugging)
railway shell
```

---

## Service Dependencies

```
PostgreSQL ─┐
Redis ──────┼─→ Backend ──→ Frontend (public URL)
MCP Weather ┘       ↑
                    │
              (API requests)
```

**Make sure:**
- Backend can connect to PostgreSQL ✅
- Backend can connect to Redis ✅
- Backend can connect to MCP Weather ✅
- Frontend can connect to Backend ✅
- Frontend has public domain ✅

---

## Environment Variable References

Railway uses `${{service.VARIABLE}}` syntax to reference other services:

```bash
# Reference database connection
${{Postgres.DATABASE_URL}}
${{Redis.REDIS_URL}}

# Reference other services (internal networking)
${{backend.RAILWAY_PRIVATE_DOMAIN}}
${{frontend.RAILWAY_PRIVATE_DOMAIN}}
${{mcp-weather.RAILWAY_PRIVATE_DOMAIN}}

# Reference public domains
${{frontend.RAILWAY_PUBLIC_DOMAIN}}
```

---

## Health Check URLs

After deployment, check these:

```bash
# Backend health
https://<backend-url>/healthz

# Frontend health (Streamlit)
https://<frontend-url>/_stcore/health

# Expected responses:
Backend: {"status":"healthy","database":"connected","redis":"connected"}
Frontend: HTTP 200 OK
```

---

## Cost Monitoring

Monitor your usage:
1. Go to Railway dashboard
2. Click "Usage" tab
3. Check current month's usage

**Optimization tips:**
- Use smaller database instances
- Set resource limits
- Monitor OpenAI API usage
- Use caching aggressively

---

## Quick Commands

```bash
# Generate JWT keys (run locally first!)
python3 scripts/generate_keys.py

# Push to GitHub (triggers Railway deploy)
git push origin main

# Link to Railway project
railway link

# Run migrations
railway run alembic upgrade head

# Seed database
railway run python seed_db.py

# View logs in real-time
railway logs -f

# Backup database
railway run pg_dump > backup.sql
```

---

## Checklist for Successful Deployment

- [ ] All 5 services created (3 app + 2 databases)
- [ ] Backend Dockerfile path set correctly
- [ ] Frontend Dockerfile path set correctly
- [ ] MCP Dockerfile path set correctly
- [ ] PostgreSQL provisioned
- [ ] Redis provisioned
- [ ] All backend env vars set (including JWT keys!)
- [ ] Frontend env var set (BACKEND_URL)
- [ ] MCP env var set (WEATHER_API_KEY)
- [ ] Frontend public domain generated
- [ ] All services deployed successfully (green checkmark)
- [ ] Database migrations run
- [ ] Database seeded
- [ ] Backend health check passes
- [ ] Can access frontend URL
- [ ] Can create account
- [ ] Can login
- [ ] Can generate travel plan

---

**If all checkboxes are ✅, you're live! 🎉**

**Still having issues?** See [RAILWAY_QUICKSTART.md](RAILWAY_QUICKSTART.md) for detailed troubleshooting.
