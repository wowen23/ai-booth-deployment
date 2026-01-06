# START HERE - AI Photo Booth Quick Start Guide

**Last Updated:** January 6, 2026
**Branch:** deployment
**Status:** ✅ Fully operational with Nikon Z6 II camera integration

## What This Is

An AI-powered photo booth that:
1. Captures photos from a Nikon Z6 II camera via USB
2. Applies AI style transformations using Google Gemini 2.5 Flash Image
3. Displays results in real-time on an iPad-friendly web interface
4. Perfect for events, parties, and creative photo experiences

## System Status

### ✅ Working Features
- Web UI accessible from any browser (iPad, desktop, mobile)
- Camera connection via Nikon MAID SDK
- Live view streaming from camera
- Automatic photo capture and AI processing
- Style presets (background replacement, full scene retheme)
- Automatic countdown timer for photo booth mode
- Gallery of processed images

### 🚧 In Progress
- Additional style templates
- Advanced camera settings control

## Quick Start (5 Minutes)

### Prerequisites
- Windows PC (x64)
- Nikon Z6 II camera with USB cable
- Python 3.12+ installed
- .NET 8.0 Runtime (likely already installed)

### Step 1: Start the Camera Bridge

```bash
cd bridge-dotnet/NikonBridge/bin/x64/Release/net8.0
./NikonBridge.exe
```

**What this does:**
- Starts HTTP server on port 9001
- Loads Nikon SDK DLLs (Type0029.md3, NkdPTP.dll, dnssd.dll, NkRoyalmile.dll)
- Waits for camera connection commands

**Expected output:**
```
info: Nikon SDK DLLs detected in C:\Users\...\net8.0\
info: MAID wrapper initialized successfully
info: Now listening on: http://0.0.0.0:9001
```

### Step 2: Start the Python Web Server

**In a new terminal:**

```bash
# From project root
py -3.13 -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Or simply:
```bash
python server.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Connect Your Camera

1. Connect Nikon Z6 II to PC via USB cable
2. Turn camera ON
3. Set camera to **Manual (M) mode**
4. Close any other camera software (Nikon Transfer, Lightroom, etc.)

### Step 4: Open the Web UI

**From any device on the same network:**

```
http://localhost:8000          (from the PC)
http://<PC-IP-ADDRESS>:8000    (from iPad/phone)
```

**Find your PC IP address:**
```bash
ipconfig | grep "IPv4"
```

### Step 5: Start Using the Booth

1. **Click "Connect Camera"** - Initializes SDK and detects Z6 II
2. **Click "Start Live View"** - Begins camera preview
3. **Click "Open Stream"** - Opens live MJPEG stream in new window (optional)
4. **Select a style** - Choose from "background" or "retheme" categories
5. **Click the green "SHOOT" button** - Captures photo, applies AI, displays result automatically!

## Troubleshooting

### Bridge won't start
**Problem:** DLLs missing error

**Solution:**
```bash
# Copy SDK DLLs from source to Release build
cp "S-SDKZ6_2-006BF-ALLIN/Module/Win/Binary Files/x64/Type0029.md3" "bridge-dotnet/NikonBridge/bin/x64/Release/net8.0/"
cp "S-SDKZ6_2-006BF-ALLIN/Module/Win/Binary Files/x64/NkdPTP.dll" "bridge-dotnet/NikonBridge/bin/x64/Release/net8.0/"
cp "S-SDKZ6_2-006BF-ALLIN/Module/Win/Binary Files/x64/dnssd.dll" "bridge-dotnet/NikonBridge/bin/x64/Release/net8.0/"
cp "S-SDKZ6_2-006BF-ALLIN/Module/Win/Binary Files/x64/NkRoyalmile.dll" "bridge-dotnet/NikonBridge/bin/x64/Release/net8.0/"
```

### Camera not detected
**Problem:** "Connect Camera" fails

**Solutions:**
1. Ensure camera is powered on
2. Check USB cable is connected properly
3. Close Nikon Webcam Utility, NX Tether, or Windows Camera app
4. Try disconnecting/reconnecting USB cable
5. Restart bridge server

**Check camera in Device Manager:**
- Look for "Nikon Z 6_2" under "Portable Devices"

### Python server won't start
**Problem:** `ModuleNotFoundError: No module named 'google.genai'`

**Solution:**
```bash
pip install -r requirements.txt
```

**Problem:** Port 8000 already in use

**Solution:**
```bash
# Use a different port
uvicorn server:app --host 0.0.0.0 --port 8001
```

### AI editing fails
**Problem:** API errors when processing images

**Solution:**
1. Verify `.env` file exists in project root
2. Check `GOOGLE_API_KEY` is set correctly
3. Test API key: https://aistudio.google.com/apikey
4. Check network connectivity

### Live view freezes
**Solution:**
1. Click "Stop" then "Start Live View" again
2. Check camera battery level (live view drains quickly)
3. Restart bridge server if persistent

## Configuration

### Environment Variables

**Python server** (`.env` in project root):
```env
GOOGLE_API_KEY=your_api_key_here
APP_ALLOW_ORIGINS=http://localhost:8000,http://192.168.1.100:8000
APP_PIN=optional_pin_for_security
```

**Bridge server** (`bridge-dotnet/NikonBridge/.env`):
```env
WATCH_DIR=C:\Users\willi\image_gen_deploy\input
BRIDGE_PORT=9001
BRIDGE_FPS=15
```

### Application Settings

**`config.json`** (in project root):
```json
{
  "input_dir": "input",
  "output_dir": "output",
  "archive_dir": "archive",
  "style_category": "retheme",
  "editor_model": "gemini-2.5-flash-image",
  "mode": "background"
}
```

## How It Works (Technical Overview)

### Architecture
```
[User's Browser/iPad]
        ↓ HTTP/WebSocket
[Python FastAPI Server :8000]
    ↓ Proxies SDK calls to bridge
    ↓ Calls Google Gemini API
[.NET Bridge Server :9001]
        ↓ HTTP API
[C++/CLI Wrapper (NikonMaidWrapper.dll)]
        ↓ Native SDK calls
[Nikon MAID SDK Type0029]
        ↓ USB PTP Protocol
[Nikon Z6 II Camera]
```

### Photo Processing Workflow

1. **Capture:**
   - User clicks SHOOT button
   - Web UI calls `/sdk/shoot` on Python server
   - Python proxies to bridge at `http://localhost:9001/shoot`
   - Bridge triggers camera shutter via MAID SDK
   - Image downloads to `input/` directory as JPEG

2. **AI Processing:**
   - Folder watcher detects new file in `input/`
   - Reads selected style prompt from `styles/<category>/<style>.txt`
   - Uploads image to Google Gemini 2.5 Flash Image API
   - Applies style transformation using prompt
   - Downloads result to `output/` directory
   - Archives original to `archive/` directory

3. **Display:**
   - Web UI polls for new images in `output/`
   - Displays processed image in gallery
   - Auto-preview after capture (deployment branch feature)

### File Locations

```
image_gen_deploy/
├── input/              # Captured photos land here
├── output/             # AI-processed results
├── archive/            # Original photos after processing
├── styles/
│   ├── background/     # Background replacement styles
│   └── retheme/        # Full scene transformation styles
├── static/
│   └── index.html      # Web UI
├── server.py           # Python FastAPI server
├── genai_client.py     # Google Gemini API wrapper
└── bridge-dotnet/
    └── NikonBridge/
        └── bin/x64/Release/net8.0/
            ├── NikonBridge.exe          # Camera bridge
            ├── NikonMaidWrapper.dll     # C++/CLI wrapper
            ├── Type0029.md3             # Nikon SDK module
            ├── NkdPTP.dll               # USB driver
            ├── dnssd.dll                # DNS service
            └── NkRoyalmile.dll          # Protocol handler
```

## Creating Custom Styles

### Background Replacement Style

Create `styles/background/my-style.txt`:
```
Keep the person exactly as they are but replace the background with [your description].
Maintain the person's position, pose, clothing, and lighting.
Only change what's behind them to create [your scene].
```

### Full Retheme Style

Create `styles/retheme/my-theme.txt`:
```
Transform this photo into [your theme/style].
[Describe the artistic style, mood, color palette, etc.]
Be creative while maintaining the core composition.
```

**Reload styles:** Refresh the web page to see new styles in dropdown.

## Advanced Usage

### Running as Windows Service

For production deployments, consider running the bridge as a Windows Service:

1. Install NSSM (Non-Sucking Service Manager)
2. Create service: `nssm install NikonBridge "C:\path\to\NikonBridge.exe"`
3. Set startup directory
4. Configure auto-restart on failure

### HTTPS for iPad Camera Access

Modern browsers require HTTPS for camera access. Use Cloudflare Tunnel:

```bash
cloudflared tunnel --url http://localhost:8000
```

Access via the generated `*.trycloudflare.com` URL.

### Multiple Camera Support (Future)

Currently supports one Nikon Z6 II at a time. For multiple cameras:
- Run multiple bridge instances on different ports
- Modify Python server to load-balance or select camera

## What Just Happened (Setup Summary)

When I set up this system, I:

1. **Copied Nikon SDK DLLs** from `S-SDKZ6_2-006BF-ALLIN/Module/Win/Binary Files/x64/` to the Release build output directory
2. **Started the .NET bridge** which loads the MAID SDK and initializes the camera wrapper
3. **Started the Python server** using Python 3.13 and uvicorn
4. **Verified both servers** are running and can communicate
5. **Tested the status endpoints** to confirm SDK DLLs are loaded

**Both servers are now ready** to handle camera operations and AI processing!

## Next Steps

### For Events
- Test end-to-end with camera connected
- Create custom style prompts for your event theme
- Print QR code pointing to web UI for guests
- Set up iPad kiosk mode for unattended operation

### For Development
- See `docs/SDK_IMPLEMENTATION_PROGRESS.md` for SDK integration details
- See `CLAUDE.md` for comprehensive developer guide
- See `docs/PHASE4_WEB_PLAN.md` for web architecture
- See `docs/SDK_BRIDGE_PLAN.md` for bridge architecture

## Getting Help

### Check Server Logs

**Bridge logs:**
- Console output where you ran `NikonBridge.exe`
- Look for SDK error codes and connection messages

**Python server logs:**
- Console output where you ran `uvicorn`
- Shows API requests and AI processing status

### Test Endpoints Manually

**Bridge health check:**
```bash
curl http://localhost:9001/status
```

**Python server health check:**
```bash
curl http://localhost:8000/health
```

**Connect camera:**
```bash
curl -X POST http://localhost:9001/sdk/connect
```

### Common Error Codes

**Bridge errors:**
- `Port already in use` - Kill old bridge process or use different port
- `DLL not found` - Copy SDK DLLs to output directory
- `Camera not found` - Check USB connection and exclusive access

**Python errors:**
- `Module not found` - Run `pip install -r requirements.txt`
- `API key invalid` - Check `.env` file GOOGLE_API_KEY
- `Connection refused` - Ensure bridge is running on port 9001

## Documentation Index

- **START_HERE.md** (this file) - Quick start guide
- **CLAUDE.md** - Comprehensive developer documentation
- **docs/INSTRUCTIONS.md** - Original handoff document
- **docs/SDK_IMPLEMENTATION_PROGRESS.md** - Camera SDK integration progress
- **docs/SDK_BRIDGE_PLAN.md** - Bridge architecture design
- **docs/PHASE4_WEB_PLAN.md** - Web application design
- **docs/MAID3*.txt** - Nikon SDK API reference (auto-generated from PDFs)

## Support

For issues or questions:
1. Check this guide's Troubleshooting section
2. Review `CLAUDE.md` for detailed architecture info
3. Check server console logs for errors
4. Verify all prerequisites are met

---

**You're all set!** Connect your camera and start creating AI-enhanced photos! 📸✨
