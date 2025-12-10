# 🎨 Render.com Deployment Guide - Complete Setup

**Estimated Time: 15-20 minutes**  
**Cost: Free tier available, or ~$21/month for always-on**

---

## 📋 Prerequisites

Before you start:

1. ✅ GitHub account with your code pushed
2. ✅ OpenAI API key ([Get one](https://platform.openai.com/api-keys))
3. ✅ JWT keys generated (run: `python3 scripts/generate_keys.py`)
4. ✅ Weather API key (optional) ([Get one](https://www.weatherapi.com/))

---

## 🚀 Step-by-Step Deployment

### Step 1: Sign Up for Render

1. Go to **[render.com](https://render.com)**
2. Click **"Get Started for Free"**
3. Sign up with your **GitHub account** (easiest option)
4. Authorize Render to access your GitHub repositories

### Step 2: Create New Blueprint

1. Once logged in, click **"New +"** button (top right)
2. Select **"Blueprint"**
3. You'll see "Connect a repository"

### Step 3: Connect Your Repository

1. Click **"Connect account"** if GitHub isn't connected
2. Search for **"KeyveveTakeHome"** repository
3. Click **"Connect"** next to your repository
4. Render will automatically detect `render.yaml` in your repo
5. You should see a preview showing:
   - ✅ backend (Web Service)
   - ✅ frontend (Web Service)
   - ✅ mcp-weather (Web Service)
   - ✅ triply-postgres (PostgreSQL Database)
   - ✅ triply-redis (Redis)

### Step 4: Configure Environment Variables

Render will show you a form to enter environment variables. Here's what to add:

#### For All Services

Click on each service and add these variables:

**OPENAI_API_KEY** (Required):
```
sk-your-actual-openai-key-here
```

**WEATHER_API_KEY** (Optional):
```
your-weather-api-key-here
```

**JWT_PRIVATE_KEY_PEM** (Required):
```
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA... (paste your full private key here)
...
-----END RSA PRIVATE KEY-----
```

**JWT_PUBLIC_KEY_PEM** (Required):
```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A... (paste your full public key here)
...
-----END PUBLIC KEY-----
```

💡 **Tip**: Render supports multi-line variables - just paste the entire key including BEGIN/END markers!

### Step 5: Review and Apply

1. Review all services in the preview
2. Click **"Apply"** button at the bottom
3. Render will start creating all services automatically

You'll see:
```
✅ Creating triply-postgres database...
✅ Creating triply-redis...
✅ Creating mcp-weather service...
✅ Creating backend service...
✅ Creating frontend service...
```

### Step 6: Wait for Deployment

Render will now:
1. ✅ Provision databases (1-2 minutes)
2. ✅ Build Docker images (5-8 minutes)
3. ✅ Deploy all services
4. ✅ Set up internal networking

**Total time: ~10-15 minutes**

You can watch progress in the dashboard. Each service will show:
- 🔵 **Building** - Docker image being built
- 🟡 **Deploying** - Service starting up
- 🟢 **Live** - Service is running!

### Step 7: Get Your App URL

Once frontend shows **🟢 Live**:

1. Click on **"frontend"** service in dashboard
2. At the top, you'll see your app URL:
   ```
   https://your-app-name.onrender.com
   ```
3. **This is your public app URL!** 🎉

### Step 8: Run Database Migrations

Once backend is deployed and shows **🟢 Live**:

1. Click on **"backend"** service
2. Click on **"Shell"** tab (left sidebar)
3. Wait for shell to connect
4. Run these commands:

```bash
# Run migrations
alembic upgrade head

# Seed database with initial data
python seed_db.py
```

You should see output like:
```
INFO  [alembic.runtime.migration] Running upgrade -> abc123
INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456
✓ Migrations complete!
```

### Step 9: Test Your Deployment

1. Visit your frontend URL: `https://your-app.onrender.com`
2. You should see the Triply Travel Planner home page!
3. Click **"Sign Up"** and create an account
4. Try generating a travel plan

**If everything works, you're live!** 🎉

---

## 📊 Service Configuration Summary

After deployment, you'll have:

| Service | Status | URL | Purpose |
|---------|--------|-----|---------|
| **frontend** | 🟢 Live | `https://your-app.onrender.com` | User interface |
| **backend** | 🟢 Live | `https://your-backend.onrender.com` | API server |
| **mcp-weather** | 🟢 Live | Internal only | Weather service |
| **triply-postgres** | 🟢 Live | Internal only | Database |
| **triply-redis** | 🟢 Live | Internal only | Cache |

---

## 💰 Render Pricing

### Free Tier
- ✅ Free for 90 days (new users)
- ✅ Services spin down after 15 minutes of inactivity
- ✅ ~30 second cold start when waking up
- ✅ Good for testing and demos

### Paid Plans (After Free Tier)

| Service | Plan | Cost |
|---------|------|------|
| Web Services (3x) | Starter | $7/month each = $21/month |
| PostgreSQL | Starter | $7/month |
| Redis | Starter | $10/month |
| **Total** | | **~$38/month** |

**Cost Optimization Tips:**
- Use free tier for testing first
- Deploy only backend + frontend (skip MCP weather)
- Use Upstash Redis (free tier) instead of Render Redis
- Use Neon PostgreSQL (free tier) instead

---

## 🔧 Post-Deployment Configuration

### Add Custom Domain (Optional)

1. Click on **frontend** service
2. Go to **"Settings"** tab
3. Scroll to **"Custom Domain"**
4. Click **"Add Custom Domain"**
5. Enter your domain (e.g., `triply.yourdomain.com`)
6. Follow DNS instructions
7. Render provides free SSL automatically!

### Set Up Monitoring

1. Each service has a **"Metrics"** tab
2. View:
   - CPU usage
   - Memory usage
   - Request count
   - Response times

### Enable Auto-Deploy

Render automatically deploys when you push to GitHub!

1. Make changes to your code
2. `git push origin main`
3. Render detects the push and redeploys automatically
4. No manual intervention needed!

---

## 🐛 Troubleshooting

### Frontend shows "Build failed"

**Check:**
1. Click service → "Logs" tab
2. Look for error messages
3. Common issue: Missing environment variables

**Fix:**
- Go to service → "Environment" tab
- Add missing variables
- Click "Manual Deploy" → "Deploy latest commit"

### Backend shows "Deploy failed"

**Check:**
1. View logs in "Logs" tab
2. Common issues:
   - Missing `OPENAI_API_KEY`
   - Invalid JWT keys
   - Database connection error

**Fix:**
- Verify all environment variables are set
- Check JWT keys include BEGIN/END markers
- Ensure database is running (should be green)

### "Health check failed"

**Check:**
1. Service → "Settings" → "Health Check Path"
2. Should be:
   - Backend: `/healthz`
   - Frontend: `/_stcore/health`

**Fix:**
- Update health check path if needed
- Redeploy service

### Database connection error

**Check:**
1. PostgreSQL service is running (green)
2. Backend environment has `POSTGRES_URL`

**Fix:**
- Render auto-configures this from `render.yaml`
- If missing, go to backend → Environment
- Add: `POSTGRES_URL` (get from database service details)

### Service is slow to start

**Free tier limitation:**
- Services sleep after 15 minutes
- First request takes ~30 seconds to wake up
- Upgrade to paid plan for always-on

---

## ✅ Deployment Checklist

After completing all steps, verify:

- [ ] All 5 services show 🟢 **Live** status
- [ ] Frontend has public URL
- [ ] Backend has public URL (or internal)
- [ ] Database migrations ran successfully
- [ ] Database seeded with initial data
- [ ] Can access frontend URL
- [ ] Can create account
- [ ] Can login
- [ ] Can generate travel plan
- [ ] Can upload PDF to knowledge base

---

## 🎯 Quick Commands Reference

### View Logs
```bash
# In Render dashboard:
Service → Logs tab → View real-time logs
```

### Run Migrations
```bash
# In backend Shell tab:
alembic upgrade head
python seed_db.py
```

### Manual Redeploy
```bash
# In service dashboard:
Manual Deploy → Deploy latest commit
```

### Rollback Deployment
```bash
# In service dashboard:
Deploys → Click on previous deploy → Redeploy
```

---

## 🔄 Updating Your App

To update your application after making changes:

```bash
# 1. Make your changes locally
# 2. Commit and push
git add .
git commit -m "Update feature"
git push origin main

# 3. Render auto-deploys!
# Watch progress in dashboard
```

---

## 📚 Additional Resources

- **Render Docs**: https://render.com/docs
- **Render Support**: https://render.com/support
- **Community Forum**: https://community.render.com
- **Status Page**: https://status.render.com

---

## 🆘 Still Having Issues?

### Check Service Health
```
Frontend: https://your-app.onrender.com/_stcore/health
Backend: https://your-backend.onrender.com/healthz
```

### Common Error Solutions

**"This site can't be reached"**
- Service is still building or starting
- Wait 2-3 minutes and refresh

**"Application error"**
- Check service logs
- Verify environment variables
- Check database is connected

**"502 Bad Gateway"**
- Service crashed or not responding
- Check logs for errors
- Redeploy if needed

---

## 🎉 Success!

Once everything is green and working:

1. ✅ Your app is live at: `https://your-app.onrender.com`
2. ✅ Share it with friends!
3. ✅ Add it to your portfolio
4. ✅ Tweet about it!

**Congratulations on deploying your AI travel planner!** 🚀✈️🌍

---

## 💡 Tips for Production

1. **Use paid plan** for always-on services
2. **Set up monitoring** with UptimeRobot
3. **Enable auto-deploy** for continuous deployment
4. **Add custom domain** for professional look
5. **Monitor costs** in Render billing dashboard
6. **Set up alerts** for service failures
7. **Backup database** regularly

---

**You're all set! Follow the steps above and you'll have your app live in 15-20 minutes.** 🎯
