# 🚀 Deployment Guide - Triply Travel Planner

This guide covers deploying your Triply application for production use with minimal cost.

## 📋 Table of Contents
1. [Deployment Options Comparison](#deployment-options-comparison)
2. [Recommended: Railway.app Deployment](#recommended-railwayapp-deployment)
3. [Alternative: Render.com Deployment](#alternative-rendercom-deployment)
4. [Alternative: DigitalOcean App Platform](#alternative-digitalocean-app-platform)
5. [Budget Option: Self-Hosted VPS](#budget-option-self-hosted-vps)
6. [Post-Deployment Steps](#post-deployment-steps)

---

## 🔍 Deployment Options Comparison

| Platform | Monthly Cost | Ease of Use | Best For |
|----------|-------------|-------------|----------|
| **Railway.app** | ~$5-15 | ⭐⭐⭐⭐⭐ Easiest | Hobby projects, startups |
| **Render.com** | ~$7-20 | ⭐⭐⭐⭐ Easy | Small teams |
| **DigitalOcean** | ~$12-25 | ⭐⭐⭐ Medium | Scalable apps |
| **Fly.io** | ~$10-20 | ⭐⭐⭐ Medium | Global distribution |
| **VPS (Self-hosted)** | ~$5-12 | ⭐⭐ Hard | Cost-conscious developers |

---

## 🎯 Recommended: Railway.app Deployment

**Cost Estimate**: $5-10/month for hobby use (free tier available)

### Why Railway?
- ✅ Native docker-compose support
- ✅ One-click PostgreSQL & Redis
- ✅ Automatic SSL
- ✅ GitHub integration
- ✅ Simple environment management
- ✅ Free $5 credit monthly (Hobby plan)

### Prerequisites
- GitHub account
- Railway account (sign up at [railway.app](https://railway.app))
- Your environment variables ready

### Step 1: Prepare Your Repository

1. **Create `.gitignore`** (if not exists):
```bash
echo ".env
.env.local
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
uploads/
*.log
.DS_Store" > .gitignore
```

2. **Commit and push to GitHub**:
```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

### Step 2: Railway Setup

1. **Go to [Railway.app](https://railway.app)** and sign in with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

3. **Add Database Services**
   - Click "New" → "Database" → "Add PostgreSQL"
   - Click "New" → "Database" → "Add Redis"
   - Railway will automatically create connection URLs

4. **Configure Environment Variables**
   
   For the **backend** service, add these variables:
   ```
   POSTGRES_URL=${{Postgres.DATABASE_URL}}
   REDIS_URL=${{Redis.REDIS_URL}}
   OPENAI_API_KEY=your_openai_api_key_here
   WEATHER_API_KEY=your_weather_api_key_here
   JWT_PRIVATE_KEY_PEM=your_jwt_private_key_here
   JWT_PUBLIC_KEY_PEM=your_jwt_public_key_here
   UI_ORIGIN=${{frontend.RAILWAY_PUBLIC_DOMAIN}}
   MCP_WEATHER_ENDPOINT=http://mcp-weather:3001
   MCP_ENABLED=true
   ENABLE_PDF_OCR=true
   OCR_DPI_SCALE=2.0
   ```

   For the **frontend** service:
   ```
   BACKEND_URL=${{backend.RAILWAY_PRIVATE_DOMAIN}}:8000
   ```

5. **Deploy Each Service**
   - Railway will auto-detect Dockerfiles
   - Deploy in this order:
     1. PostgreSQL (database)
     2. Redis (database)
     3. mcp-weather (Node.js service)
     4. backend (FastAPI)
     5. frontend (Streamlit)

6. **Generate Domain**
   - Click on frontend service
   - Go to "Settings" → "Public Networking"
   - Click "Generate Domain"
   - Your app will be live at: `https://your-app.railway.app`

### Step 3: Run Database Migrations

Once backend is deployed:

1. Go to backend service in Railway
2. Click "Deployments" → Latest deployment → "View Logs"
3. Or use Railway CLI to run migrations:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# Run migrations
railway run alembic upgrade head

# Seed database
railway run python seed_db.py
```

### Step 4: Verify Deployment

Visit your frontend URL and check:
- [ ] Frontend loads correctly
- [ ] Can create an account
- [ ] Can login
- [ ] Can create a travel plan
- [ ] Backend health check: `https://your-backend.railway.app/healthz`

---

## 🔄 Alternative: Render.com Deployment

**Cost Estimate**: $7-20/month

### Why Render?
- Simple setup
- Good free tier
- Auto-scaling
- Background workers support

### Quick Setup

1. **Create `render.yaml`** (see file in repo)
2. Go to [Render.com](https://render.com)
3. "New" → "Blueprint"
4. Connect GitHub repo
5. Render will read `render.yaml` and deploy all services

### Pricing on Render
- Web Services: $7/month each (2 services = $14)
- PostgreSQL: $7/month
- Redis: $10/month
- **Total**: ~$21/month

---

## 🌊 Alternative: DigitalOcean App Platform

**Cost Estimate**: $12-25/month

### Why DigitalOcean?
- Reliable infrastructure
- Easy scaling
- Good documentation
- Managed databases

### Quick Setup

1. **Create account** at [DigitalOcean.com](https://digitalocean.com)
2. Go to "App Platform"
3. Connect GitHub
4. DigitalOcean auto-detects Dockerfiles
5. Add managed PostgreSQL database ($15/month)
6. Add managed Redis ($15/month or use free tier alternatives)

### Cost Optimization
- Use Basic plan for services ($5 each)
- Use Dev database for PostgreSQL ($7/month)
- Use Upstash Redis (free tier) instead of managed

---

## 💰 Budget Option: Self-Hosted VPS

**Cost Estimate**: $5-12/month (cheapest but requires more work)

### Recommended Providers
1. **Hetzner Cloud** - €4.15/month (best value)
2. **DigitalOcean Droplet** - $6/month
3. **Linode** - $5/month
4. **Vultr** - $6/month

### Requirements
- 2 GB RAM minimum (4 GB recommended)
- 2 vCPU
- 50 GB storage
- Ubuntu 22.04 LTS

### Setup Script

I've created an automated setup script for VPS deployment:

```bash
# SSH into your VPS
ssh root@your_vps_ip

# Download and run setup script
curl -sSL https://raw.githubusercontent.com/your-repo/main/scripts/vps-setup.sh | bash
```

See `scripts/vps-setup.sh` in this repo for the full script.

### Manual VPS Setup

1. **Install Docker & Docker Compose**:
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Install system dependencies for PDF OCR
sudo apt-get install -y tesseract-ocr poppler-utils
```

2. **Clone your repository**:
```bash
git clone https://github.com/your-username/KeyveveTakeHome.git
cd KeyveveTakeHome
```

3. **Create `.env` file**:
```bash
cp .env.example .env
nano .env  # Edit with your values
```

4. **Deploy**:
```bash
docker-compose up -d
```

5. **Setup Nginx reverse proxy** (for SSL):
```bash
sudo apt install nginx certbot python3-certbot-nginx -y

# Create Nginx config
sudo nano /etc/nginx/sites-available/triply

# Add configuration (see nginx.conf in repo)

sudo ln -s /etc/nginx/sites-available/triply /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com
```

6. **Run migrations**:
```bash
docker-compose exec backend alembic upgrade head
docker-compose exec backend python seed_db.py
```

---

## 🔐 Environment Variables Setup

You'll need these environment variables regardless of platform:

### Required Variables

```bash
# Database
POSTGRES_URL=postgresql://user:password@host:5432/triply
POSTGRES_PASSWORD=your_secure_password_here

# Redis
REDIS_URL=redis://host:6379/0

# OpenAI API (for embeddings and LLM)
OPENAI_API_KEY=sk-your-key-here

# Weather API (optional, for MCP server)
WEATHER_API_KEY=your_weather_api_key

# JWT Keys (generate with: python scripts/generate_keys.py)
JWT_PRIVATE_KEY_PEM="-----BEGIN RSA PRIVATE KEY-----
...your key here...
-----END RSA PRIVATE KEY-----"

JWT_PUBLIC_KEY_PEM="-----BEGIN PUBLIC KEY-----
...your key here...
-----END PUBLIC KEY-----"

# CORS
UI_ORIGIN=https://your-frontend-domain.com

# Optional: PDF OCR
ENABLE_PDF_OCR=true
OCR_DPI_SCALE=2.0
OCR_MIN_TEXT_THRESHOLD=50
```

### Generate JWT Keys

Run this locally to generate RSA keys:

```bash
python scripts/generate_keys.py
```

Copy the output into your environment variables.

---

## 📊 Post-Deployment Steps

### 1. Health Check
```bash
curl https://your-backend-url.com/healthz
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "mcp_weather": "available"
}
```

### 2. Create Initial Admin User

SSH/exec into backend container:
```bash
# Railway
railway run python -c "from backend.app.db.seed import create_admin; create_admin()"

# Docker
docker-compose exec backend python -c "from backend.app.db.seed import create_admin; create_admin()"
```

### 3. Test Authentication
```bash
curl -X POST https://your-backend-url.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your_password"}'
```

### 4. Upload Knowledge Base

Use the Streamlit UI:
1. Login with admin account
2. Go to "Knowledge Management"
3. Create a destination
4. Upload PDF/MD travel guides

### 5. Monitor Logs

**Railway**: Click service → "Deployments" → "View Logs"

**Render**: Click service → "Logs"

**VPS**: 
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

---

## 🔧 Troubleshooting

### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Database connection - verify POSTGRES_URL
# 2. Missing migrations - run: alembic upgrade head
# 3. Invalid JWT keys - regenerate with scripts/generate_keys.py
```

### Frontend can't connect to backend
```bash
# Check BACKEND_URL environment variable
# Should be: http://backend:8000 (Docker internal)
# Or: https://your-backend-url.com (external)
```

### Database migration fails
```bash
# Reset database (CAUTION: deletes data)
docker-compose down -v
docker-compose up -d postgres
docker-compose exec backend alembic upgrade head
```

### Out of memory errors
```bash
# Increase container memory limits in docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

---

## 💡 Cost Optimization Tips

1. **Use Free Tiers**:
   - OpenAI: Use gpt-4o-mini instead of gpt-4 (10x cheaper)
   - Weather API: Use free tier (often 1000 calls/day)
   - Redis: Use Upstash free tier (10k commands/day)

2. **Scale Down for Hobby Use**:
   - Set aggressive rate limits
   - Use smaller database instances
   - Disable MCP server if not needed

3. **Monitor Usage**:
   - Set up billing alerts
   - Track OpenAI API usage
   - Use caching aggressively

4. **Optimize Resources**:
   ```yaml
   # docker-compose.yml
   services:
     backend:
       deploy:
         resources:
           limits:
             cpus: '0.5'
             memory: 512M
   ```

---

## 📝 Maintenance

### Regular Updates
```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose up -d --build
```

### Backup Database
```bash
# Automated daily backup script
docker-compose exec postgres pg_dump -U postgres triply > backup_$(date +%Y%m%d).sql
```

### Monitor Health
Set up uptime monitoring:
- [UptimeRobot](https://uptimerobot.com) - Free
- [Better Uptime](https://betteruptime.com) - Free tier
- Ping `/healthz` endpoint every 5 minutes

---

## 🎓 Next Steps

1. Choose your deployment platform (recommend Railway for simplicity)
2. Gather all environment variables
3. Generate JWT keys
4. Deploy following the guide above
5. Run database migrations
6. Create admin user
7. Upload knowledge base documents
8. Share your app URL!

---

## 🆘 Need Help?

If you encounter issues:
1. Check the logs first
2. Verify all environment variables are set
3. Ensure external APIs (OpenAI, Weather) are working
4. Check database connectivity
5. Review the troubleshooting section above

---

**Estimated Total Deployment Time**: 30-60 minutes (Railway/Render) or 2-3 hours (VPS)

**Recommended for Beginners**: Railway.app
**Recommended for Budget**: Hetzner VPS
**Recommended for Scale**: DigitalOcean App Platform
