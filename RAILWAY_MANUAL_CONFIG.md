# 🚨 RAILWAY DEPLOYMENT FIX - Manual Configuration Required

## The Problem

Railway is **NOT automatically detecting** the `railway.*.json` config files. You need to configure each service **manually in the Railway dashboard**.

## ✅ Solution: Configure Each Service Manually

Follow these exact steps for each service:

---

## Step 1: Configure Backend Service

1. **In Railway Dashboard**, click on your **backend** service
2. Go to **Settings** tab
3. Scroll to **Build** section
4. Click **Configure** or **Edit Build Settings**
5. Set these values:

   ```
   Builder: Dockerfile
   Dockerfile Path: backend/Dockerfile
   Root Directory: (leave blank or set to /)
   ```

   **Important**: Use `backend/Dockerfile` NOT `./backend/Dockerfile`

6. Click **Save** or **Update**
7. Go to **Variables** tab and add environment variables (see below)
8. Click **Deploy** to redeploy

---

## Step 2: Configure Frontend Service

1. Click on your **frontend** service
2. Go to **Settings** tab
3. Scroll to **Build** section
4. Set these values:

   ```
   Builder: Dockerfile
   Dockerfile Path: frontend/Dockerfile
   Root Directory: (leave blank or set to /)
   ```

5. Click **Save**
6. Go to **Variables** tab and add:
   ```
   BACKEND_URL=http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000
   ```
7. Go to **Settings** → **Networking** → **Generate Domain**
8. Click **Deploy** to redeploy

---

## Step 3: Configure MCP Weather Service

1. Click on your **mcp-weather** service
2. Go to **Settings** tab
3. Scroll to **Build** section
4. Set these values:

   ```
   Builder: Dockerfile
   Dockerfile Path: mcp-server/Dockerfile
   Root Directory: (leave blank or set to /)
   ```

5. Click **Save**
6. Go to **Variables** tab and add:
   ```
   WEATHER_API_KEY=your-weather-api-key-here
   PORT=3001
   ```
7. Click **Deploy** to redeploy

---

## Step 4: Verify All Services

After configuring all three services:

1. Check that each service shows **Dockerfile Path** correctly in Settings
2. Make sure all environment variables are set
3. Each service should rebuild and deploy successfully

---

## Backend Environment Variables

In Backend service → Variables tab, add:

```bash
POSTGRES_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
OPENAI_API_KEY=sk-your-actual-key-here
WEATHER_API_KEY=your-weather-key-here
JWT_PRIVATE_KEY_PEM=-----BEGIN RSA PRIVATE KEY-----
(paste your full private key here with line breaks)
-----END RSA PRIVATE KEY-----
JWT_PUBLIC_KEY_PEM=-----BEGIN PUBLIC KEY-----
(paste your full public key here with line breaks)
-----END PUBLIC KEY-----
MCP_WEATHER_ENDPOINT=http://${{mcp-weather.RAILWAY_PRIVATE_DOMAIN}}:3001
UI_ORIGIN=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}
MCP_ENABLED=true
ENABLE_PDF_OCR=true
OCR_DPI_SCALE=2.0
```

**Important**: Railway supports multi-line environment variables. Paste the entire JWT key including the BEGIN/END markers and line breaks.

---

## Why This is Needed

Railway doesn't automatically read `railway.*.json` files from your repo. These files are templates for reference only. You must configure each service manually in the Railway dashboard.

---

## Alternative: Use Railway CLI

If you prefer, you can use Railway CLI to configure services:

```bash
# Install CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# Set service context
railway service

# Then configure via CLI or dashboard
```

However, **using the dashboard is simpler** for initial setup.

---

## Checklist

For each service, verify:

- [ ] **Backend**:
  - [ ] Dockerfile Path: `backend/Dockerfile`
  - [ ] Root Directory: blank or `/`
  - [ ] All environment variables set
  - [ ] Deployed successfully

- [ ] **Frontend**:
  - [ ] Dockerfile Path: `frontend/Dockerfile`
  - [ ] Root Directory: blank or `/`
  - [ ] BACKEND_URL variable set
  - [ ] Public domain generated
  - [ ] Deployed successfully

- [ ] **MCP Weather**:
  - [ ] Dockerfile Path: `mcp-server/Dockerfile`
  - [ ] Root Directory: blank or `/`
  - [ ] WEATHER_API_KEY and PORT set
  - [ ] Deployed successfully

- [ ] **PostgreSQL**: Database added
- [ ] **Redis**: Database added

---

## After All Services Are Deployed

Run database migrations:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link
railway login
railway link

# Select backend service
railway service

# Run migrations
railway run alembic upgrade head
railway run python seed_db.py
```

---

## Still Getting Errors?

### Error: "Dockerfile does not exist"
- Check that Dockerfile Path is **exactly**: `backend/Dockerfile` (no `./` prefix)
- Root Directory should be blank or `/`
- Make sure you're editing the correct service

### Error: "No such file or directory"
- The path might be case-sensitive
- Verify: `backend/Dockerfile` not `Backend/Dockerfile`

### Error: Build timeout
- Your service might need more resources
- Check Settings → Resources and increase if needed

---

## Visual Guide

Here's what your Settings → Build section should look like:

```
Service Settings
├── Build
│   ├── Builder: Dockerfile
│   ├── Dockerfile Path: backend/Dockerfile    ← KEY SETTING
│   └── Root Directory: /                       ← KEY SETTING
├── Deploy
│   └── Start Command: (auto-detected)
└── Variables
    └── (your environment variables)
```

---

## Next Steps

1. ✅ Configure all 3 services with correct Dockerfile paths
2. ✅ Set all environment variables
3. ✅ Generate public domain for frontend
4. ✅ Wait for all deployments to complete
5. ✅ Run database migrations
6. ✅ Test your app!

**This should fix the Dockerfile error!** 🚀
