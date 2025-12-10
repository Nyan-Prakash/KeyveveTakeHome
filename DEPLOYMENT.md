# Keyveve Travel Planner - Railway Deployment Guide

Complete guide to deploy your Keyveve AI Travel Planner to the internet using Railway.app.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Step 1: Prepare Your Environment](#step-1-prepare-your-environment)
- [Step 2: Create Railway Account](#step-2-create-railway-account)
- [Step 3: Deploy to Railway](#step-3-deploy-to-railway)
- [Step 4: Configure Services](#step-4-configure-services)
- [Step 5: Test Your Deployment](#step-5-test-your-deployment)
- [Troubleshooting](#troubleshooting)
- [Cost Estimates](#cost-estimates)

---

## Prerequisites

Before you begin, make sure you have:

1. **GitHub Account** - Railway connects to your GitHub repo
2. **OpenAI API Key** - Get from [OpenAI Platform](https://platform.openai.com/api-keys)
3. **Weather API Key** - Get free key from [OpenWeatherMap](https://openweathermap.org/api)
4. **Your local project working** - Test with `docker-compose up` first

---

## Step 1: Prepare Your Environment

### 1.1 Get Your API Keys

**OpenAI API Key:**
1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-proj-...`)
5. **Important**: Add credits to your OpenAI account

**Weather API Key:**
1. Go to https://openweathermap.org/api
2. Sign up for a free account
3. Go to API keys section
4. Copy the API key (you already have: `13ec1d0233b566d7b3e41bfbe84ebea3`)

### 1.2 Verify JWT Keys

Your JWT keys are already configured in your `.env` file. You'll need to copy them to Railway later.

Open `.env` and locate:
- `JWT_PRIVATE_KEY_PEM`
- `JWT_PUBLIC_KEY_PEM`

### 1.3 Test Locally First

Before deploying, make sure everything works locally:

```bash
# Start all services
docker-compose up --build

# In a new terminal, test the health endpoints
curl http://localhost:8000/healthz          # Backend
curl http://localhost:8501/_stcore/health   # Frontend
curl http://localhost:3001/health           # MCP Server
```

If all three return healthy responses, you're ready to deploy!

---

## Step 2: Create Railway Account

### 2.1 Sign Up
1. Go to https://railway.app
2. Click "Start a New Project"
3. Sign up with your GitHub account
4. Verify your email address
5. Add a payment method (required after free trial)

### 2.2 Install Railway CLI (Optional but Helpful)
```bash
# Install via npm
npm install -g @railway/cli

# Or via homebrew (macOS)
brew install railway

# Login to Railway
railway login
```

---

## Step 3: Deploy to Railway

### 3.1 Push Your Code to GitHub

If you haven't already:

```bash
# Add all deployment files
git add .
git commit -m "Add Railway deployment configuration"
git push origin main
```

### 3.2 Create New Railway Project

#### Option A: Via Railway Dashboard (Easiest)

1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Select your repository: `KeyveveTakeHome`
4. Railway will detect your Docker setup automatically

#### Option B: Via Railway CLI

```bash
# From your project directory
railway init
railway link
```

### 3.3 Add Database Services

Railway needs separate services for PostgreSQL and Redis:

**Add PostgreSQL:**
1. In your Railway project dashboard, click "New"
2. Select "Database" → "Add PostgreSQL"
3. Railway provisions it automatically
4. **Important**: After provisioning, you need to enable pgvector extension

**Add Redis:**
1. Click "New" again
2. Select "Database" → "Add Redis"
3. Railway provisions it automatically

---

## Step 4: Configure Services

Railway will create 5 services total:
- `postgres` (Database)
- `redis` (Cache)
- `backend` (API)
- `frontend` (UI)
- `mcp-weather` (Weather service)

### 4.1 Configure Backend Service

Click on the `backend` service and add these environment variables:

```bash
# Copy from your .env file
OPENAI_API_KEY=sk-proj-YOUR-KEY-HERE
WEATHER_API_KEY=your-weather-key-here
JWT_PRIVATE_KEY_PEM=<paste your entire private key including BEGIN/END lines>
JWT_PUBLIC_KEY_PEM=<paste your entire public key including BEGIN/END lines>

# Railway auto-provides these - use Railway's variable references
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}

# Will update this after frontend deploys
UI_ORIGIN=${{frontend.RAILWAY_STATIC_URL}}

# Internal service URLs (Railway handles networking)
MCP_WEATHER_ENDPOINT=http://mcp-weather:3001

# Optional settings
OPENAI_MODEL=gpt-4-turbo-preview
MCP_ENABLED=true
FANOUT_CAP=4
AIRPORT_BUFFER_MIN=120
TRANSIT_BUFFER_MIN=15
FX_TTL_HOURS=24
WEATHER_TTL_HOURS=24
```

**Important**:
- For `JWT_PRIVATE_KEY_PEM` and `JWT_PUBLIC_KEY_PEM`, paste the ENTIRE key including the `-----BEGIN` and `-----END` lines
- Use Railway's variable reference syntax: `${{Postgres.DATABASE_URL}}`

### 4.2 Configure Frontend Service

Click on the `frontend` service and add:

```bash
# Use Railway's internal networking
BACKEND_URL=${{backend.RAILWAY_STATIC_URL}}
```

### 4.3 Configure MCP Weather Service

Click on the `mcp-weather` service and add:

```bash
WEATHER_API_KEY=your-weather-key-here
PORT=3001
REDIS_URL=${{Redis.REDIS_URL}}
```

### 4.4 Enable pgvector Extension

**This is critical for the RAG functionality to work!**

1. In Railway dashboard, click on your PostgreSQL service
2. Click "Connect" → "Connect via psql"
3. Railway will open a terminal connection
4. Run this command:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
5. Verify it worked:
   ```sql
   \dx
   ```
   You should see `vector` in the list of extensions

### 4.5 Configure Service Settings

For each service (backend, frontend, mcp-weather):

1. Click on the service
2. Go to "Settings"
3. Set the correct Dockerfile path:
   - **Backend**: Root directory `/` with Dockerfile `backend/Dockerfile`
   - **Frontend**: Root directory `/` with Dockerfile `frontend/Dockerfile`
   - **MCP Weather**: Root directory `/` with Dockerfile `mcp-server/Dockerfile`

### 4.6 Update UI_ORIGIN

After the frontend deploys, Railway will assign it a URL like:
`https://keyveve-frontend-production.up.railway.app`

1. Copy this URL
2. Go back to backend service environment variables
3. Update `UI_ORIGIN` to this URL
4. Redeploy the backend service

---

## Step 5: Test Your Deployment

### 5.1 Check Service Health

Once all services show "Active" in Railway:

1. **Backend Health Check:**
   - Find your backend URL (looks like `https://keyveve-backend.up.railway.app`)
   - Visit: `https://your-backend-url.railway.app/healthz`
   - Should return: `{"status": "healthy"}`

2. **Frontend Health Check:**
   - Find your frontend URL
   - Visit: `https://your-frontend-url.railway.app/_stcore/health`
   - Should return: `ok`

3. **MCP Server Health Check:**
   - Find your MCP server URL
   - Visit: `https://your-mcp-url.railway.app/health`
   - Should return: `{"status": "healthy"}`

### 5.2 Test the Application

1. **Access the Frontend:**
   - Go to your frontend URL
   - You should see the Keyveve home page

2. **Sign Up / Login:**
   - Create a new user account
   - Test the login flow

3. **Create a Travel Plan:**
   - Try creating a simple travel plan
   - Check that it generates an itinerary

4. **Test Chat Interface:**
   - Go to the Chat page
   - Send a message about travel planning
   - Verify you get AI responses

### 5.3 Check Logs

If anything isn't working:

1. In Railway dashboard, click on the service
2. Go to "Logs" tab
3. Look for error messages

Common things to check:
- Database connection successful?
- Redis connection successful?
- API keys valid?
- Migrations ran successfully?

---

## Troubleshooting

### Database Connection Errors

**Problem**: Backend logs show "could not connect to database"

**Solutions**:
1. Verify `DATABASE_URL` in backend environment variables
2. Make sure PostgreSQL service is healthy (green checkmark)
3. Check PostgreSQL logs for errors
4. Verify the format: `postgresql://user:pass@host:port/db`

### Redis Connection Errors

**Problem**: Backend logs show "could not connect to Redis"

**Solutions**:
1. Verify `REDIS_URL` in backend environment variables
2. Make sure Redis service is healthy
3. Check format: `redis://host:port`

### CORS Errors

**Problem**: Frontend shows CORS errors in browser console

**Solutions**:
1. Make sure `UI_ORIGIN` in backend matches your frontend URL exactly
2. Include `https://` and no trailing slash
3. Redeploy backend after changing `UI_ORIGIN`
4. Clear browser cache

### Build Failures

**Problem**: Service fails to deploy

**Solutions**:
1. Check Railway build logs for specific error
2. Verify Dockerfile path is set correctly
3. Make sure all dependencies are in `requirements.txt` or `package.json`
4. Check that Docker builds locally: `docker build -f backend/Dockerfile .`

### Migration Failures

**Problem**: Backend starts but database tables missing

**Solutions**:
1. Check backend logs for migration errors
2. Manually run migrations via Railway shell:
   ```bash
   railway shell backend
   alembic upgrade head
   ```
3. Verify pgvector extension is installed

### OpenAI API Errors

**Problem**: Travel planning fails with API errors

**Solutions**:
1. Verify `OPENAI_API_KEY` is correct
2. Check OpenAI account has credits
3. Check API usage limits at https://platform.openai.com/usage
4. Review backend logs for specific error message

### MCP Server Not Reachable

**Problem**: Weather data not working

**Solutions**:
1. Check MCP server is deployed and healthy
2. Verify `MCP_WEATHER_ENDPOINT` uses internal Railway URL: `http://mcp-weather:3001`
3. Check weather API key is valid
4. Review MCP server logs

### Service Won't Start

**Problem**: Service keeps crashing/restarting

**Solutions**:
1. Check the service logs for startup errors
2. Verify all required environment variables are set
3. Check health check configuration
4. Increase health check `start_period` if service is slow to start

---

## Cost Estimates

### Railway Pricing

Railway uses a usage-based pricing model:

**Free Trial:**
- $5 in credits when you sign up
- Good for ~500 execution hours
- Perfect for initial testing

**Estimated Monthly Costs (after free trial):**

| Service | Resource | Estimated Cost |
|---------|----------|----------------|
| Backend | 1 GB RAM, 1 vCPU | ~$5-8/month |
| Frontend | 512 MB RAM, 0.5 vCPU | ~$3-5/month |
| MCP Server | 256 MB RAM, 0.5 vCPU | ~$2-3/month |
| PostgreSQL | 1 GB storage | ~$5/month |
| Redis | 256 MB storage | ~$3/month |
| **Total** | | **~$18-24/month** |

**Additional Costs:**
- **Bandwidth**: First 100 GB free, then $0.10/GB
- **Builds**: First 500 minutes free, then $0.05/minute

### External API Costs

**OpenAI API** (Pay-as-you-go):
- GPT-4 Turbo: ~$0.01 per 1K input tokens, ~$0.03 per 1K output tokens
- Embeddings: ~$0.0001 per 1K tokens
- **Estimated**: $10-50/month depending on usage

**Weather API**:
- Free tier: 60 calls/minute, 1M calls/month
- **Cost**: $0 (free tier should be sufficient)

### Cost Optimization Tips

1. **Use Railway's sleep feature** - Put services to sleep when not in use
2. **Monitor usage** - Check Railway dashboard regularly
3. **Optimize Docker images** - Smaller images = faster builds = lower costs
4. **Cache dependencies** - Reduce build times
5. **Set usage alerts** - Railway can notify you of high usage

---

## Next Steps

### Add a Custom Domain (Optional)

1. Buy a domain from Namecheap, Google Domains, etc.
2. In Railway, go to your frontend service
3. Click "Settings" → "Domains"
4. Add your custom domain
5. Update DNS records as instructed by Railway
6. Update `UI_ORIGIN` in backend to use your custom domain

### Setup Monitoring

Railway provides built-in monitoring:
- CPU usage
- Memory usage
- Request logs
- Error tracking
- Uptime monitoring

Access via your service dashboard.

### Automatic Deployments

Railway automatically redeploys when you push to your main branch:

```bash
git add .
git commit -m "Update feature"
git push origin main
```

Railway will detect the push and redeploy automatically.

### Backup Your Database

1. In Railway, click on PostgreSQL service
2. Go to "Settings" → "Backups"
3. Enable automatic daily backups
4. Or manually backup via Railway CLI:
   ```bash
   railway pg dump
   ```

### Environment Management

Create separate Railway projects for different environments:
- **Production**: Connected to `main` branch
- **Staging**: Connected to `staging` branch
- **Development**: Your local Docker setup

---

## Support

If you run into issues:

1. **Check Railway's Status**: https://status.railway.app
2. **Railway Discord**: https://discord.gg/railway
3. **Railway Docs**: https://docs.railway.app
4. **Your Application Logs**: Always check service logs first

---

## Summary

You've successfully deployed Keyveve Travel Planner! 🎉

Your application is now accessible at:
- **Frontend**: `https://your-app-name.up.railway.app`
- **Backend API**: `https://your-backend.up.railway.app`
- **API Docs**: `https://your-backend.up.railway.app/docs`

Key features now live:
✅ AI-powered travel planning
✅ RAG-enhanced recommendations
✅ Real-time chat interface
✅ Weather integration
✅ Multi-day itinerary generation
✅ User authentication
✅ Knowledge base management

**Estimated Monthly Cost**: $20-30 for demo/personal use

Share your frontend URL with others to let them try your travel planner!
