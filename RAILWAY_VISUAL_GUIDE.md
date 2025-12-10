# 🎯 Railway Configuration - Visual Guide

## Where to Configure Dockerfile Path

```
Railway Dashboard
└── Your Project
    └── backend service                    ← CLICK HERE
        ├── Deployments
        ├── Variables
        └── Settings                       ← CLICK HERE
            └── Build                      ← SCROLL TO THIS SECTION
                ├── Builder: [Dockerfile]  ← SELECT "Dockerfile"
                ├── Dockerfile Path: [    ] ← TYPE: backend/Dockerfile
                └── Root Directory: [    ]  ← LEAVE BLANK or type /
```

## What You Need to Change

### ❌ Current (Not Working)
Railway is looking for: `./Dockerfile` in root directory

### ✅ What You Need to Set

**For Backend Service:**
```
Dockerfile Path: backend/Dockerfile
```

**For Frontend Service:**
```
Dockerfile Path: frontend/Dockerfile
```

**For MCP Weather Service:**
```
Dockerfile Path: mcp-server/Dockerfile
```

## Step-by-Step Screenshots Guide

### 1. Select Service
```
┌─────────────────────────────────────┐
│  Your Railway Project               │
├─────────────────────────────────────┤
│  [backend]  ← CLICK THIS            │
│  [frontend]                         │
│  [mcp-weather]                      │
│  [Postgres]                         │
│  [Redis]                            │
└─────────────────────────────────────┘
```

### 2. Go to Settings Tab
```
┌─────────────────────────────────────┐
│  backend                            │
├─────────────────────────────────────┤
│  Deployments  Variables  [Settings] │← CLICK
└─────────────────────────────────────┘
```

### 3. Find Build Section
```
Settings
├── General
├── [Build]  ← SCROLL TO THIS
├── Deploy
├── Networking
└── Danger
```

### 4. Configure Build Settings
```
Build
┌─────────────────────────────────────┐
│ Builder:         [Dockerfile ▼]    │
│                                     │
│ Dockerfile Path: [backend/Dockerfile] ← TYPE THIS
│                                     │
│ Root Directory:  [/              ] │ ← LEAVE BLANK or /
│                                     │
│ [Save Changes]                      │
└─────────────────────────────────────┘
```

### 5. Redeploy
```
┌─────────────────────────────────────┐
│  Changes saved!                     │
│  [Redeploy Now]  ← CLICK THIS      │
└─────────────────────────────────────┘
```

## Quick Copy-Paste Values

### Backend Service
```
Dockerfile Path: backend/Dockerfile
Root Directory: /
```

### Frontend Service
```
Dockerfile Path: frontend/Dockerfile
Root Directory: /
```

### MCP Weather Service
```
Dockerfile Path: mcp-server/Dockerfile
Root Directory: /
```

## Verification Checklist

After configuration, check:

- [ ] Settings → Build → Dockerfile Path is set correctly
- [ ] No `./` prefix in the path
- [ ] Root Directory is blank or `/`
- [ ] Service redeployed successfully
- [ ] Build logs show correct Dockerfile being used

## Expected Build Log Output

After correct configuration, you should see:

```
✓ Initialization
✓ Build > Build image
  Building from Dockerfile: backend/Dockerfile  ← Should show this
  Step 1/10 : FROM python:3.11-slim
  ...
✓ Deploy
✓ Post-deploy
```

## Common Mistakes to Avoid

❌ **Don't use**: `./backend/Dockerfile`  
✅ **Use**: `backend/Dockerfile`

❌ **Don't set Root Directory to**: `backend/`  
✅ **Leave blank or set to**: `/`

❌ **Don't forget to**: Click Save/Update  
✅ **Always**: Save changes and redeploy

## All Three Services Configured?

Once all three services show these settings:

```
✓ backend     → backend/Dockerfile
✓ frontend    → frontend/Dockerfile
✓ mcp-weather → mcp-server/Dockerfile
```

Then your deployments should succeed! 🎉

## Need More Help?

See: [RAILWAY_MANUAL_CONFIG.md](RAILWAY_MANUAL_CONFIG.md) for detailed step-by-step instructions.
