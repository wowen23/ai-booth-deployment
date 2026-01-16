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

**Why this architecture?** Python cannot directly call Nikon's native SDK. The C++/CLI wrapper exposes the SDK as a managed .NET assembly, the .NET bridge provides an HTTP API, and Python FastAPI proxies requests while handling AI processing.

**Image flow:** Camera → `input/` dir → Gemini AI → `output/` dir → QR code/email delivery → Gallery UI

**Platform constraints:** x64 Windows only (Nikon SDK). Camera requires exclusive USB access.

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

Or with explicit Python version:
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

**Terminal 3 - Cloudflare Tunnel (optional, for HTTPS):**
```bash
cloudflared tunnel --url http://localhost:8000
```

**Web UI:** http://localhost:8000

### Kill stuck processes (PowerShell)
```powershell
taskkill /F /IM NikonBridge.exe
taskkill /F /IM python.exe
```

## Key Files

### Python Backend

- **server.py** - Main FastAPI server (port 8000)
  - `/edit` - AI style transformation via Gemini
  - `/sdk/*` - Proxy to .NET bridge
  - `/watcher/*` - Folder watcher control
  - `/galleries/*` - Photo gallery management
  - `/send-email`, `/send-sms` - Photo delivery
  - Serves static UI from `static/index.html`

- **genai_client.py** - `edit_with_gemini_image()` - Gemini API wrapper
- **watcher.py** - Monitors `input/` for new images, auto-processes with AI
- **qr_generator.py** - QR code generation for photo sharing
- **email_sender.py** - Email delivery via SMTP

### .NET Bridge

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

- **static/index.html** - Vanilla JS SPA with tabs (AI Booth, Settings)
  - Responsive for iPad/tablet kiosk use

## Configuration

### Environment Files

**.env** (root) - Python server:
- `GOOGLE_API_KEY` - Required for Gemini API
- `APP_ALLOW_ORIGINS` - CORS origins (comma-separated)
- `APP_PIN` - Optional PIN for /edit endpoint

**bridge-dotnet/NikonBridge/.env** - Bridge server:
- `WATCH_DIR` - Where captured images save (must match Python input_dir)
- `BRIDGE_PORT` - Default 9001
- `BRIDGE_FPS` - Live view frame rate (default 15)

Note: Bridge `.env` must be copied to output directory (`bin/x64/Release/net8.0/`)

### config.json

```json
{
  "input_dir": "input",
  "output_dir": "output",
  "archive_dir": "archive",
  "editor_model": "gemini-2.5-flash-image"
}
```

### Style System

Styles are `.txt` prompt templates in `styles/`:
- `styles/background/` - Replace background, keep subject
- `styles/retheme/` - Transform entire scene

## Nikon SDK

**Location:** `S-SDKZ6_2-006BF-ALLIN/`
- Docs: `Module/Documents/English/` (MAID3*.pdf)
- Binaries: `Module/Win/Bin/x64/`

**Key concepts:**
- Live view and capture mode are mutually exclusive - must stop live view before shooting
- Image download is async via data event callbacks
- Camera connection lost if USB disconnects or camera powers off

## Implementation Notes

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

No automated tests. Manual testing:
```bash
curl http://localhost:9001/status  # Bridge health
curl http://localhost:8000/health  # Python health
```

## Related Documentation

- `docs/START_HERE.md` - Quick start guide
- `docs/ez_start_instructions.md` - Simplified startup steps
- `docs/ENVIRONMENT_VARIABLES.md` - Full env var reference
- `docs/SDK_BRIDGE_PLAN.md` - Bridge architecture
- `docs/PHASE4_WEB_PLAN.md` - Web app design
