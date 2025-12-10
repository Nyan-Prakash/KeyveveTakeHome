# 🚂 Railway.app Quick Start Guide

**Deploy your Triply Travel Planner in 15 minutes!**

Railway is the **fastest and easiest** way to deploy this application. Perfect for personal projects and hobby use.

## 💰 Cost Estimate
- **Free Tier**: $5 credit per month (enough for light use)
- **Hobby Plan**: $5/month base + usage (~$5-10 total for this app)
- **Estimated Monthly Cost**: $5-15

## 📋 Prerequisites

1. **GitHub Account** - [Sign up](https://github.com/signup) if you don't have one
2. **Railway Account** - [Sign up](https://railway.app) (free, use GitHub to sign in)
3. **API Keys Ready**:
   - OpenAI API key ([Get one](https://platform.openai.com/api-keys))
   - Weather API key (optional) ([Get one](https://www.weatherapi.com/))

## 🚀 Deployment Steps

### Step 1: Prepare Your Repository

```bash
# If you haven't already, commit and push to GitHub
cd /Users/nyanprakash/Desktop/Keyveve/Attempt2/KeyveveTakeHome
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

### Step 2: Generate JWT Keys

**Important**: You need RSA keys for authentication.

```bash
# Generate keys
python3 scripts/generate_keys.py

# Copy the output - you'll need it in Step 4
```

Expected output:
```
JWT_PRIVATE_KEY_PEM="-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"

JWT_PUBLIC_KEY_PEM="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A...
-----END PUBLIC KEY-----"
```

**Save these somewhere safe!** You'll paste them into Railway.

### Step 3: Deploy on Railway

1. **Go to [Railway.app](https://railway.app)** and sign in with GitHub

2. **Create New Project**
   - Click the "New Project" button
   - Select "Deploy from GitHub repo"
   - Choose your `KeyveveTakeHome` repository
   - Click "Deploy Now"

3. **Add PostgreSQL Database**
   - Click "+ New" button in your project
   - Select "Database" → "Add PostgreSQL"
   - Railway will provision it automatically
   - Name it: `postgres`

4. **Add Redis Database**
   - Click "+ New" button again
   - Select "Database" → "Add Redis"
   - Railway will provision it automatically
   - Name it: `redis`

### Step 4: Configure Services

Railway will detect your Dockerfiles. You need to configure each service:

#### 4a. Configure Backend Service

1. Click on the **backend** service
2. Go to **Settings** tab
3. Set **Start Command** (if needed):
   ```
   alembic upgrade head && uvicorn backend.app.main:create_app --host 0.0.0.0 --port $PORT --factory
   ```
4. Go to **Variables** tab
5. Click "New Variable" and add these one by one:

```bash
# Database URLs (use Railway references)
POSTGRES_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}

# Your API keys
OPENAI_API_KEY=sk-your-actual-openai-key-here
WEATHER_API_KEY=your-weather-api-key-here

# JWT Keys (paste from Step 2)
JWT_PRIVATE_KEY_PEM=-----BEGIN RSA PRIVATE KEY-----
YOUR_PRIVATE_KEY_HERE
-----END RSA PRIVATE KEY-----

JWT_PUBLIC_KEY_PEM=-----BEGIN PUBLIC KEY-----
YOUR_PUBLIC_KEY_HERE  
-----END PUBLIC KEY-----

# Service URLs (use Railway references)
MCP_WEATHER_ENDPOINT=http://${{mcp-weather.RAILWAY_PRIVATE_DOMAIN}}:3001
UI_ORIGIN=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}

# Configuration
MCP_ENABLED=true
ENABLE_PDF_OCR=true
OCR_DPI_SCALE=2.0
```

**Important**: For `JWT_PRIVATE_KEY_PEM` and `JWT_PUBLIC_KEY_PEM`, include the full key with line breaks. Railway supports multi-line variables.

#### 4b. Configure Frontend Service

1. Click on the **frontend** service
2. Go to **Variables** tab
3. Add:

```bash
BACKEND_URL=http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000
```

#### 4c. Configure MCP Weather Service

1. Click on the **mcp-weather** service
2. Go to **Variables** tab
3. Add:

```bash
WEATHER_API_KEY=your-weather-api-key-here
PORT=3001
```

### Step 5: Generate Public Domain

1. Click on the **frontend** service
2. Go to **Settings** tab
3. Scroll to **Networking** section
4. Click **Generate Domain**
5. Railway will assign you a URL like: `your-app-production.up.railway.app`

**This is your app URL!** 🎉

### Step 6: Deploy and Monitor

1. Railway will automatically deploy all services
2. Watch the **Deployments** tab for progress
3. Check logs if anything fails

### Step 7: Run Database Migrations

Once backend is deployed:

**Option A: Using Railway CLI (Recommended)**

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Run migrations
railway run alembic upgrade head

# Seed database
railway run python seed_db.py
```

**Option B: Using Railway Dashboard**

1. Go to backend service
2. Click on **Deployments** tab
3. Click **"..."** on latest deployment
4. Select **"New Ephemeral Environment"**
5. Run command: `alembic upgrade head`
6. Run command: `python seed_db.py`

### Step 8: Verify Deployment

1. **Check Health**
   - Backend: Click backend service → **Settings** → Copy URL → Add `/healthz`
   - Should see: `{"status":"healthy","database":"connected",...}`

2. **Test Frontend**
   - Go to your frontend URL (from Step 5)
   - You should see the Triply home page!

3. **Create Account**
   - Click "Sign Up"
   - Create your first user
   - Start planning trips!

## ✅ Deployment Checklist

- [ ] Repository pushed to GitHub
- [ ] JWT keys generated and saved
- [ ] Railway project created
- [ ] PostgreSQL database added
- [ ] Redis database added
- [ ] Backend environment variables configured
- [ ] Frontend environment variables configured
- [ ] MCP weather environment variables configured
- [ ] Public domain generated for frontend
- [ ] All services deployed successfully
- [ ] Database migrations run
- [ ] Database seeded
- [ ] Health check passes
- [ ] Can create account and login

## 🔧 Troubleshooting

### Backend won't deploy

**Check logs:**
1. Go to backend service
2. Click **"Deployments"** tab
3. Click on the latest deployment
4. Click **"View Logs"**

**Common issues:**
- Missing environment variables
- Invalid JWT keys (must include BEGIN/END lines)
- Database connection error (check POSTGRES_URL)

### Frontend can't connect to backend

**Fix:**
1. Go to frontend service
2. Check **Variables** tab
3. Make sure `BACKEND_URL` is set to: `http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000`
4. Redeploy frontend service

### Database migrations failed

**Run manually:**
```bash
railway link
railway run alembic upgrade head
```

Or use the Railway dashboard ephemeral environment method.

### "Insufficient credits" error

**Solution:**
- Upgrade to Hobby plan ($5/month)
- Or optimize resource usage by scaling down services

## 💡 Post-Deployment Tips

### Monitor Usage
1. Go to your project dashboard
2. Click **"Usage"** tab
3. Monitor your monthly usage and costs

### View Logs
```bash
# Using CLI
railway logs

# Or click service → Deployments → View Logs
```

### Update Your App
```bash
# Make changes locally
git add .
git commit -m "Update feature"
git push origin main

# Railway auto-deploys on push!
```

### Backup Database
```bash
# Export database
railway run pg_dump > backup.sql

# Import database
railway run psql < backup.sql
```

### Add Custom Domain (Optional)
1. Click frontend service
2. Go to **Settings** → **Networking**
3. Click **"Custom Domain"**
4. Follow instructions to add your domain
5. Railway handles SSL automatically!

## 📊 Monitoring

### Setup Uptime Monitoring (Free)

1. **Go to [UptimeRobot.com](https://uptimerobot.com)**
2. Sign up for free account
3. Add HTTP(s) monitor
4. URL: `https://your-app.railway.app/healthz`
5. Check interval: 5 minutes
6. Get email alerts if app goes down

### Railway Metrics

Railway provides:
- CPU usage
- Memory usage
- Network bandwidth
- Request count
- Response times

Access in: Project → Service → **Metrics** tab

## 🎓 Next Steps

1. **Upload Knowledge Base**
   - Login to your app
   - Go to "Knowledge Management"
   - Create destinations
   - Upload travel guides (PDF, MD)

2. **Customize Settings**
   - Adjust rate limits
   - Configure user permissions
   - Set up additional features

3. **Share Your App**
   - Your app is now live!
   - Share the URL with friends
   - Start planning trips

## 💰 Cost Optimization

### Stay Within Free Tier
- Use gpt-4o-mini instead of gpt-4 (10x cheaper)
- Set aggressive rate limits
- Use hobby PostgreSQL plan
- Monitor usage weekly

### Estimated Costs Breakdown
- **Compute**: ~$3-5/month (3 services)
- **PostgreSQL**: ~$0-5/month (depends on size)
- **Redis**: ~$0-3/month (usually free tier)
- **Bandwidth**: ~$0-2/month (low traffic)
- **Total**: **$5-15/month**

## 🆘 Need Help?

### Railway Support
- [Railway Docs](https://docs.railway.app)
- [Railway Discord](https://discord.gg/railway)
- [Railway Help Center](https://help.railway.app)

### App Issues
1. Check the logs first
2. Verify environment variables
3. Test health endpoint
4. Check database connectivity

## 🎉 Success!

Your Triply Travel Planner is now live on Railway! 

**Share your deployment:**
- Tweet about it
- Add to your portfolio
- Share with friends

**Your app URL:** `https://your-app.railway.app`

Happy traveling! ✈️🌍
