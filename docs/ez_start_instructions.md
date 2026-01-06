# Quick Start - AI Photo Booth

## First Time / Troubleshooting

If you get "port already in use" error, kill existing processes:

**PowerShell:**
```powershell
taskkill /F /IM NikonBridge.exe
taskkill /F /IM python.exe
```

**Git Bash:**
```bash
taskkill //F //IM NikonBridge.exe
taskkill //F //IM python.exe
```

---

## Start Both Servers

### Terminal 1 - Camera Bridge Server
```bash
cd bridge-dotnet/NikonBridge/bin/x64/Release/net8.0
./NikonBridge.exe
```

Should see:
```
[MAID] Initializing Nikon SDK...
Nikon Bridge running at http://localhost:9001
```

---

### Terminal 2 - Python Web Server
```bash
py -3.13 -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Terminal 3 - Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
``` 

## Access the App

Open in browser: **http://localhost:8000**

---

## Usage

1. Click "Connect Camera" to initialize Nikon Z6 II
2. Click green "SHOOT" button to capture photo
3. AI will automatically process the photo
4. QR code will pop up for guests to scan

---

## Stop Servers

Press `Ctrl+C` in each terminal window
