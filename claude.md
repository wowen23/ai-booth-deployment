# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered photo booth that captures from a Nikon Z6 II camera via USB and applies AI style transformations using Google Gemini. Multi-layer architecture: Python FastAPI web server → .NET bridge → C++/CLI wrapper → Nikon MAID SDK.

## Architecture

```
[Nikon Z6 II Camera via USB]
        ↓
[C++/CLI Wrapper (NikonMaidWrapper.dll)] ← Nikon MAID SDK Type0029
        ↓
[.NET Bridge Server (port 9001)] ← ASP.NET Core HTTP API
        ↓
[Python FastAPI Server (port 8000)] ← Main web server + Gemini AI
        ↓
[Web UI Browser (static/index.html)]
```

### Key Architecture Points

1. **Three-layer bridge design**: Python cannot directly call Nikon's native SDK, so:
   - C++/CLI wrapper exposes SDK as managed .NET assembly
   - .NET bridge provides HTTP API for camera control
   - Python FastAPI proxies requests to bridge and handles AI processing

2. **Image flow**: Camera → `input/` dir → Folder watcher → Gemini AI → `output/` dir → Gallery UI

3. **Live view streaming**: Bridge captures frames from SDK and serves as MJPEG stream at `/live.mjpg`

4. **Platform constraints**:
   - x64 architecture required (Nikon SDK is 64-bit only)
   - Windows-only (Nikon MAID SDK is Windows-native)
   - USB exclusive access (camera must not be open in other software)

## Build Commands

### .NET Bridge (Release)

```bash
"C:\Program Files\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe" NikonBridge.sln /p:Configuration=Release /p:Platform=x64
```

Or open `bridge-dotnet/NikonBridge/NikonBridge.sln` in Visual Studio 2022.

**Build requirements:**
- x64 platform (not AnyCPU) - Nikon SDK is 64-bit only
- C++/CLI wrapper builds first, then .NET project references it
- Nikon SDK DLLs must be in output directory: `NkdPTP.dll`, `dnssd.dll`, `NkRoyalmile.dll`, `Type0029.md3`
- Copy DLLs from `S-SDKZ6_2-006BF-ALLIN/Module/Win/Bin/x64/`

### Python Server

```bash
pip install -r requirements.txt
python server.py
```

Or with explicit uvicorn (recommended for reliability):
```bash
py -3.13 -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Server starts on http://localhost:8000

**Install dependencies:**
```bash
py -3.13 -m uvicorn server:app --host 0.0.0.0 --port 8000
```

## Development Workflow

### Startup Sequence

**Terminal 1 - Camera Bridge:**
```bash
cd bridge-dotnet/NikonBridge/bin/x64/Release/net8.0
./NikonBridge.exe
```

**Terminal 2 - Python Server:**
```bash
python server.py
```

4. **Open web UI**: http://localhost:8000

### Camera operation workflow:

1. Connect Nikon Z6 II via USB, power on
2. In web UI, click "Connect Camera" → initializes SDK
3. Click "Start Live View" → begins live view mode
4. Click "Open Stream" → opens MJPEG stream in new window
5. Click "SHOOT" button (green) → captures photo, auto-processes with AI, displays result
6. Alternative: Click "Shoot" in SDK section → captures without auto-processing

## Key Files and Their Responsibilities

### Python Backend (FastAPI)

- **server.py** (529 lines) - Main HTTP server
  - `/edit` - Apply AI style transformation to uploaded image
  - `/styles` - List available style prompts by category
  - `/prompts` - Create new style prompt file
  - `/sdk/*` - Proxy endpoints to .NET bridge
  - `/watcher/*` - Control folder watcher daemon
  - Serves static UI from `static/index.html`

- **genai_client.py** - Google Gemini API wrapper
  - `edit_with_gemini_image()` - Main AI editing function
  - Requires `GOOGLE_API_KEY` environment variable

- **watcher.py** - Automated folder monitoring daemon
  - Watches `input/` directory for new JPG/PNG files
  - Auto-processes through Gemini with configured style
  - Archives originals to `archive/` after processing
  - Controlled via `/watcher/start` and `/watcher/stop` endpoints

### .NET Bridge (ASP.NET Core)

- **bridge-dotnet/NikonBridge/Program.cs** - Camera HTTP API (port 9001)
  - `GET /status` - Connection state
  - `GET /live.mjpg` - MJPEG live view stream
  - `POST /shoot` - Trigger shutter
  - `POST /sdk/connect`, `/sdk/disconnect` - SDK lifecycle
  - `POST /sdk/start-live`, `/sdk/stop-live` - Live view control

### C++/CLI Wrapper

- **bridge-dotnet/NikonMaidWrapper/** - `MaidBridge` class wraps Nikon MAID SDK
  - `Connect()`, `Disconnect()`, `Shoot()`, `StartLive()`, `StopLive()`, `GetLiveFrame()`

### Web Frontend

- **static/index.html** - Single-page application with tabs
  - **AI Booth tab**: Style selector, SHOOT button, file upload, results gallery
  - **Settings tab**: Configuration UI (planned)
  - SDK Live View section: Camera controls, live stream preview
  - Vanilla JavaScript (no framework)
  - Responsive design for iPad/tablet use at events

### Configuration

- **config.json** - Application settings
  - `input_dir`, `output_dir`, `archive_dir` - File paths
  - `style_category` - Default category (background/retheme)
  - `editor_model` - Gemini model to use
  - `mode` - Processing mode (background/retheme)

- **.env** (root) - Python server environment
  - `GOOGLE_API_KEY` - Google AI Studio API key
  - `APP_ALLOW_ORIGINS` - CORS allowed origins
  - `APP_PIN` - Optional PIN security for /edit endpoint

- **bridge-dotnet/NikonBridge/.env** - Bridge environment
  - `WATCH_DIR` - Where to save captured images
  - `BRIDGE_PORT` - HTTP port (default 9001)
  - `BRIDGE_FPS` - Live view frame rate

## Style System

Styles are text prompt templates stored in `styles/` directory:

- **styles/background/** - Background replacement prompts (preserve subject, change background)
- **styles/retheme/** - Full scene retheme prompts (transform entire image)

Each style is a `.txt` file containing the Gemini prompt. New styles can be created via `/prompts` endpoint or by adding files directly.

## Current Branch: deployment

This is the deployment branch with Release builds configured. Recent commits focus on:
- Release build configuration for portability
- Automatic camera reconnect after AI processing
- Automatic AI editing on SHOOT button press
- Countdown timer for photo booth UX
- Simplified UI for event deployment

Main differences from master:
- Uses Release builds of bridge
- Optimized for standalone deployment without Visual Studio
- Pre-built binaries included for target deployment environment

## Nikon SDK Integration Details

### SDK Location
- SDK package: `S-SDKZ6_2-006BF-ALLIN/` directory
- Documentation: `S-SDKZ6_2-006BF-ALLIN/Module/Documents/English/`
  - MAID3(E).pdf - Core API reference
  - MAID3Type0029(E).pdf - Type0029 USB module specifics
  - Usage of Type0029 Module(E).pdf - Integration guide
  - Type0029 Sample Guide(E).pdf - Sample code walkthrough
- Sample code: `S-SDKZ6_2-006BF-ALLIN/Module/Win/Sample Program/`

### Key SDK Concepts
- **Module**: Type0029 provides USB PTP camera communication
- **Object**: Cameras and capabilities are represented as objects with IDs
- **Capabilities**: Each object has capabilities (properties) that can be queried/set
- **Data events**: Async callbacks for image downloads and live view frames
- **Live view**: Special mode for real-time preview, separate from capture mode

## Troubleshooting

### Bridge won't start
- Verify Nikon SDK DLLs are in bridge output directory
- Check `.env` file exists with valid WATCH_DIR path
- Ensure port 9001 is not in use by another process
- Check Windows Event Viewer for DLL loading errors

### Camera not detected
- Ensure Z6 II is connected via USB and powered on
- Close any other software accessing the camera (Nikon Transfer, Lightroom, etc.)
- Check Windows Device Manager for "Nikon Z 6_2" under "Portable Devices"
- Try disconnecting/reconnecting USB cable
- Restart bridge server to reinitialize SDK

### AI editing fails
- Verify `GOOGLE_API_KEY` is set in `.env` and valid
- Check network connectivity to Google AI services
- Review `server.py` console output for API errors
- Ensure image format is JPEG or PNG
- Check Gemini API quota/rate limits

### Live view stream freezes
- Stop and restart live view from web UI
- Check bridge console for frame capture errors
- Verify camera battery is charged (live view is power-intensive)
- Try reducing BRIDGE_FPS in bridge .env file

### Build errors
- **LNK2028/LNK2001 errors**: Platform target mismatch, ensure x64 build
- **CS0006 metadata errors**: Clean solution and rebuild in correct order (C++/CLI first, then .NET)
- **DLL not found at runtime**: Copy Nikon SDK DLLs to output directory
- **C++/CLI compilation errors**: Ensure Visual Studio C++/CLI workload is installed

## Important Implementation Notes

### Camera Bridge
- Handle MAID SDK errors gracefully (many operations can fail)
- Stop live view before shooting, restart after download completes
- Image download is async via data event callbacks

### Python Server
- Folder watcher runs in separate thread
- Gemini API has 16MB image limit (auto-resized)
- WATCH_DIR in bridge must match input_dir in config.json

### Web UI
- No build step - just refresh browser
- Vanilla JS, no framework dependencies

## Testing

No automated tests currently exist. Manual testing workflow:

1. **Test bridge standalone**: Start bridge, curl `http://localhost:9001/status`
2. **Test camera connection**: Click "Connect Camera", verify status shows connected
3. **Test live view**: Start live, open stream, verify smooth video
4. **Test capture**: Click Shoot, verify image appears in input/ directory
5. **Test AI processing**: Upload image, select style, click Edit, verify output in output/
6. **Test folder watcher**: Start watcher, drop image in input/, verify auto-processing

## Deployment Checklist

- [ ] Build bridge in Release mode for x64 platform
- [ ] Copy Nikon SDK DLLs to bridge output directory
- [ ] Verify .env files exist with correct paths for target machine
- [ ] Test camera connection on target hardware
- [ ] Install Visual C++ Runtime if not present (bridge dependency)
- [ ] Configure GOOGLE_API_KEY for target environment
- [ ] Test end-to-end capture → AI → display workflow
- [ ] Verify USB cable quality (poor cables cause connection issues)

## Documentation References

- **INSTRUCTIONS.md** - Comprehensive handoff document with SDK integration details (if present in codebase)
- **docs/SDK_BRIDGE_PLAN.md** - Original bridge architecture plan
- **docs/PHASE4_WEB_PLAN.md** - Web application design document
- **Nikon SDK docs** - See S-SDKZ6_2-006BF-ALLIN/Module/Documents/English/
