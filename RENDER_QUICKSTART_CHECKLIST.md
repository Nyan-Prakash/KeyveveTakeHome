# ✅ Render.com Quick Start Checklist

## Before You Start (5 minutes)

- [ ] Generate JWT keys: `python3 scripts/generate_keys.py`
- [ ] Have OpenAI API key ready
- [ ] Code pushed to GitHub
- [ ] Have 15-20 minutes free time

---

## Deployment Steps (15 minutes)

### 1. Sign Up (2 minutes)
- [ ] Go to [render.com](https://render.com)
- [ ] Click "Get Started for Free"
- [ ] Sign up with GitHub account
- [ ] Authorize Render

### 2. Create Blueprint (1 minute)
- [ ] Click "New +" → "Blueprint"
- [ ] Connect your "KeyveveTakeHome" repository
- [ ] Render detects `render.yaml` automatically

### 3. Add Environment Variables (3 minutes)

When prompted, add these:

- [ ] `OPENAI_API_KEY` = `sk-your-key-here`
- [ ] `WEATHER_API_KEY` = `your-weather-key` (optional)
- [ ] `JWT_PRIVATE_KEY_PEM` = (paste full private key with BEGIN/END)
- [ ] `JWT_PUBLIC_KEY_PEM` = (paste full public key with BEGIN/END)

### 4. Apply Blueprint (1 minute)
- [ ] Review services preview (should show 5 services)
- [ ] Click "Apply"
- [ ] Wait for deployment to start

### 5. Wait for Build (10 minutes)
- [ ] Watch dashboard as services build
- [ ] PostgreSQL: 🟢 Live
- [ ] Redis: 🟢 Live
- [ ] MCP Weather: 🟢 Live
- [ ] Backend: 🟢 Live (this takes longest)
- [ ] Frontend: 🟢 Live

### 6. Run Migrations (2 minutes)
- [ ] Click "backend" service
- [ ] Go to "Shell" tab
- [ ] Run: `alembic upgrade head`
- [ ] Run: `python seed_db.py`

### 7. Test Your App (2 minutes)
- [ ] Get frontend URL from dashboard
- [ ] Visit: `https://your-app.onrender.com`
- [ ] Create account
- [ ] Test login
- [ ] Generate a travel plan

---

## ✅ You're Done!

**Total Time**: ~20 minutes  
**Your App URL**: `https://your-app.onrender.com`  
**Status**: 🟢 LIVE!

---

## 🎯 What to Do Now

- [ ] Share your app URL
- [ ] Add to your portfolio
- [ ] Upload travel guides to knowledge base
- [ ] Set up custom domain (optional)
- [ ] Monitor usage and costs

---

## 🆘 If Something Goes Wrong

**Service won't build?**
→ Check "Logs" tab for errors

**Missing environment variables?**
→ Go to service → "Environment" tab → Add them

**Database connection error?**
→ Ensure PostgreSQL service is 🟢 Live

**Need help?**
→ See [RENDER_DEPLOYMENT_GUIDE.md](RENDER_DEPLOYMENT_GUIDE.md)

---

**Render is MUCH easier than Railway - you got this!** 🚀
