# Environment Variables Configuration Guide

This guide explains all environment variables used by the AI Photo Booth system and how to configure them.

## Overview

The system uses **two separate `.env` files**:

1. **Root `.env`** - For the Python FastAPI server
2. **`bridge-dotnet/NikonBridge/.env`** - For the .NET camera bridge

Both are required for the system to function correctly.

---

## Python Server Environment Variables

**File Location:** `C:\Users\willi\image_gen_deploy\.env`

### Required Variables

#### GOOGLE_API_KEY
- **Description:** API key for Google AI Studio (Gemini API)
- **Required:** Yes
- **Type:** String
- **Example:** `GOOGLE_API_KEY=AIzaSyAaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQq`
- **How to get:**
  1. Visit https://aistudio.google.com/apikey
  2. Sign in with your Google account
  3. Click "Create API Key"
  4. Copy the key
- **Used by:** AI image processing (Gemini 2.5 Flash Image)

### Optional Variables

#### APP_ALLOW_ORIGINS
- **Description:** CORS allowed origins for web UI access
- **Default:** `http://localhost:8000,http://127.0.0.1:8000`
- **Type:** Comma-separated list of URLs
- **Example:** `APP_ALLOW_ORIGINS=http://localhost:8000,http://192.168.1.100:8000,http://10.0.0.5:8000`
- **When to set:** When accessing the web UI from other devices on your network
- **Usage:**
  ```env
  # Allow access from iPad on local network
  APP_ALLOW_ORIGINS=http://localhost:8000,http://192.168.1.50:8000
  ```

#### APP_PIN
- **Description:** Optional PIN for securing the `/edit` endpoint
- **Default:** None (no PIN required)
- **Type:** String
- **Example:** `APP_PIN=1234`
- **When to set:** For public/event environments where you want to restrict access
- **Usage:**
  - If set, users must provide this PIN when submitting images for AI processing
  - Useful for preventing unauthorized API usage

### Example `.env` File (Python)

```env
# Google AI Studio API Key (REQUIRED)
GOOGLE_API_KEY=AIzaSyAaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQq

# CORS Origins (optional - for iPad/network access)
APP_ALLOW_ORIGINS=http://localhost:8000,http://192.168.1.100:8000

# Security PIN (optional)
# APP_PIN=1234
```

---

## Camera Bridge Environment Variables

**File Location:** `C:\Users\willi\image_gen_deploy\bridge-dotnet\NikonBridge\.env`

**IMPORTANT:** This file must also be copied to:
- `C:\Users\willi\image_gen_deploy\bridge-dotnet\NikonBridge\bin\x64\Release\net8.0\.env`
- `C:\Users\willi\image_gen_deploy\bridge-dotnet\NikonBridge\bin\x64\Debug\net8.0\.env` (if using Debug build)

### Required Variables

#### WATCH_DIR
- **Description:** Directory where captured images will be saved
- **Required:** Yes
- **Type:** Absolute Windows path
- **Example:** `WATCH_DIR=C:\Users\willi\image_gen_deploy\input`
- **CRITICAL:** This MUST match the Python server's `input_dir` in `config.json`
- **Path format:** Use backslashes (`\`) or forward slashes (`/`)
- **Usage:**
  ```env
  # Correct - absolute path
  WATCH_DIR=C:\Users\willi\image_gen_deploy\input

  # Also works - forward slashes
  WATCH_DIR=C:/Users/willi/image_gen_deploy/input
  ```

### Optional Variables

#### BRIDGE_PORT
- **Description:** HTTP port for the camera bridge server
- **Default:** `9001`
- **Type:** Integer (1-65535)
- **Example:** `BRIDGE_PORT=9001`
- **When to change:** If port 9001 is already in use
- **Note:** If you change this, update the Python server's bridge URL configuration

#### BRIDGE_FPS
- **Description:** Target frame rate for live view streaming
- **Default:** `15`
- **Type:** Integer (1-30)
- **Example:** `BRIDGE_FPS=15`
- **When to adjust:**
  - Lower (5-10): Better for slower networks or older devices
  - Higher (20-30): Smoother live view on fast connections
  - Note: Actual FPS depends on camera and USB connection

### Example `.env` File (Bridge)

```env
# Directory where captured photos are saved (REQUIRED)
# MUST match Python server's input directory!
WATCH_DIR=C:\Users\willi\image_gen_deploy\input

# HTTP server port
BRIDGE_PORT=9001

# Live view frame rate (frames per second)
BRIDGE_FPS=15
```

---

## Complete Setup Instructions

### Step 1: Create Python Server `.env`

1. Create file at project root: `C:\Users\willi\image_gen_deploy\.env`
2. Add your Google API key:
   ```env
   GOOGLE_API_KEY=your_actual_key_here
   ```
3. (Optional) Add CORS origins if accessing from other devices
4. Save the file

### Step 2: Create Bridge `.env`

1. Create file at: `C:\Users\willi\image_gen_deploy\bridge-dotnet\NikonBridge\.env`
2. Add required configuration:
   ```env
   WATCH_DIR=C:\Users\willi\image_gen_deploy\input
   BRIDGE_PORT=9001
   BRIDGE_FPS=15
   ```
3. Save the file

### Step 3: Copy Bridge `.env` to Output Directory

**For Release build:**
```bash
cp bridge-dotnet/NikonBridge/.env bridge-dotnet/NikonBridge/bin/x64/Release/net8.0/.env
```

**For Debug build:**
```bash
cp bridge-dotnet/NikonBridge/.env bridge-dotnet/NikonBridge/bin/x64/Debug/net8.0/.env
```

**Why?** The .NET application reads the `.env` file from its working directory (where the .exe is located).

### Step 4: Verify Configuration

Check that directories exist:
```bash
# Ensure input directory exists
mkdir -p C:\Users\willi\image_gen_deploy\input
mkdir -p C:\Users\willi\image_gen_deploy\output
mkdir -p C:\Users\willi\image_gen_deploy\archive
```

---

## Troubleshooting

### "Photos not appearing in gallery"

**Problem:** Images are captured but not processed by AI

**Check:**
1. Bridge `WATCH_DIR` matches Python `config.json` `input_dir`
   ```bash
   # Bridge status
   curl http://localhost:9001/status
   # Should show: "watch_dir": "C:\\Users\\willi\\image_gen_deploy\\input"

   # Python config
   cat config.json
   # Should show: "input_dir": "input"
   ```

2. Folder watcher is running:
   ```bash
   curl http://localhost:8000/watcher/status
   # Should show: "running": true
   ```

**Solution:** Ensure paths match and restart both servers

### "Invalid API Key" errors

**Problem:** AI processing fails with authentication error

**Check:**
1. `.env` file exists in project root
2. `GOOGLE_API_KEY` is set correctly (no quotes, no spaces)
3. API key is valid at https://aistudio.google.com/apikey

**Solution:**
```bash
# Check if .env exists
ls -la .env

# View contents (be careful not to expose publicly!)
cat .env

# Test key validity
curl http://localhost:8000/health
```

### "Bridge won't start" or "Wrong watch_dir"

**Problem:** Bridge shows wrong directory or fails to start

**Check:**
1. `.env` file exists in the executable's directory
   ```bash
   # For Release build
   ls bridge-dotnet/NikonBridge/bin/x64/Release/net8.0/.env

   # View contents
   cat bridge-dotnet/NikonBridge/bin/x64/Release/net8.0/.env
   ```

2. Path uses correct format (backslashes or forward slashes)

**Solution:** Copy `.env` to output directory and restart bridge

### "CORS errors" from iPad/other devices

**Problem:** Web UI loads but can't make API requests

**Check:**
1. `APP_ALLOW_ORIGINS` includes the accessing device's URL
2. Format is correct (no trailing slashes, comma-separated)

**Solution:**
```env
# Add your iPad's IP
APP_ALLOW_ORIGINS=http://localhost:8000,http://192.168.1.100:8000
```

Restart Python server after changing.

---

## Environment Variable Priority

### Python Server
1. `.env` file in project root
2. System environment variables
3. Built-in defaults

### .NET Bridge
1. `.env` file in working directory (where .exe runs)
2. `appsettings.json` (if present)
3. System environment variables
4. Built-in defaults

---

## Security Best Practices

### ⚠️ Never Commit `.env` Files to Git

Both `.env` files are in `.gitignore` by default. Keep it that way!

**Bad:**
```bash
git add .env  # DON'T DO THIS!
```

**Good:**
```bash
# .env files are automatically ignored
git status  # Should NOT show .env files
```

### Sharing Configuration (Template Method)

**Create template files** for others:

**`.env.example`** (Python):
```env
# Copy this file to .env and fill in your values

GOOGLE_API_KEY=your_key_here
APP_ALLOW_ORIGINS=http://localhost:8000
# APP_PIN=optional_pin
```

**`bridge-dotnet/NikonBridge/.env.example`**:
```env
# Copy this file to .env and adjust paths

WATCH_DIR=C:\Users\YourUsername\image_gen_deploy\input
BRIDGE_PORT=9001
BRIDGE_FPS=15
```

Then users can:
```bash
cp .env.example .env
# Edit .env with their actual values
```

### Production Deployment

For production/event environments:

1. **Use strong PINs** if enabling `APP_PIN`
2. **Restrict CORS** to only trusted origins
3. **Store API keys securely** (use Azure Key Vault, AWS Secrets Manager, etc.)
4. **Use HTTPS** with Cloudflare Tunnel or reverse proxy
5. **Monitor API usage** to avoid quota exhaustion

---

## Quick Reference

| Variable | File | Required | Default | Purpose |
|----------|------|----------|---------|---------|
| `GOOGLE_API_KEY` | Root `.env` | ✅ Yes | None | Gemini API authentication |
| `APP_ALLOW_ORIGINS` | Root `.env` | ❌ No | localhost only | CORS allowed origins |
| `APP_PIN` | Root `.env` | ❌ No | None | Security PIN |
| `WATCH_DIR` | Bridge `.env` | ✅ Yes | `./output` | Image save location |
| `BRIDGE_PORT` | Bridge `.env` | ❌ No | `9001` | HTTP server port |
| `BRIDGE_FPS` | Bridge `.env` | ❌ No | `15` | Live view frame rate |

---

## Getting Help

If you're still having issues after following this guide:

1. **Check server logs** for error messages
2. **Verify file locations** with the commands above
3. **Test endpoints** manually with curl
4. **Review START_HERE.md** for troubleshooting section

---

**Last Updated:** January 6, 2026
