# AI Photo Booth with Nikon Camera Integration

## Project Overview

An AI-powered photo booth application that captures images from a Nikon Z6 II camera and applies AI-driven style transformations using Google Gemini. The system consists of a Python web application, a .NET bridge for camera control, and a C++/CLI wrapper around the Nikon MAID SDK.

## Architecture

```
[Nikon Z6 II Camera]
        ↓ USB
[C++/CLI Wrapper] ← Nikon MAID SDK Type0029
        ↓
[.NET Bridge Server] ← HTTP API (port 9001)
        ↓
[Python FastAPI Server] ← HTTP API (port 8000)
        ↓ WebSocket/HTTP
[Web UI Browser]
```

### Components

1. **Web Application (Python + FastAPI)**
   - Main user interface and API server
   - AI image processing with Google Gemini 2.5 Flash Image
   - Folder watcher for automated processing
   - Style management (background replacement, full retheme)

2. **Camera Bridge (.NET 8.0 + C++/CLI)**
   - HTTP server exposing camera controls
   - Wraps Nikon MAID SDK for camera communication
   - Provides live view streaming and capture endpoints

3. **AI Processing**
   - Google Gemini 2.5 Flash Image for style transfer
   - Custom prompt templates in `styles/` directory
   - Support for background replacement and full scene retheme

## Directory Structure

```
image_gen/
├── bridge-dotnet/           # .NET camera bridge
│   ├── NikonBridge/         # ASP.NET Core HTTP server
│   │   ├── Program.cs       # Main server with endpoints
│   │   └── .env            # Bridge configuration
│   ├── NikonMaidWrapper/    # C++/CLI wrapper for Nikon SDK
│   │   ├── NikonMaidWrapper.h
│   │   └── NikonMaidWrapper.cpp
│   └── Wrapper2/            # Additional wrapper project
├── static/                  # Web UI (HTML/CSS/JS)
│   └── index.html          # Main web interface
├── styles/                  # Prompt templates
│   ├── background/         # Background replacement styles
│   └── retheme/           # Full scene retheme styles
├── input/                  # Watch directory for new photos
├── output/                 # AI-processed images
├── archive/                # Processed originals
├── docs/                   # Documentation
│   ├── SDK_BRIDGE_PLAN.md
│   └── PHASE4_WEB_PLAN.md
├── S-SDKZ6_2-006BF-ALLIN/ # Nikon SDK package
├── server.py              # Main FastAPI server
├── genai_client.py        # Google Gemini API wrapper
├── watcher.py             # Folder watcher daemon
├── bridge.py              # Legacy OpenCV bridge (prototype)
├── generate_image.py      # CLI for image generation
├── gui.py                 # PySide6 desktop GUI
├── config.json            # Application configuration
├── requirements.txt       # Python dependencies
└── .env                   # API keys and settings
```

## Key Files

### Python Backend

- **server.py** (529 lines) - Main FastAPI server with all endpoints
  - Image editing API (`/edit`)
  - Style management (`/styles`, `/prompts`)
  - Folder watcher control (`/watcher/*`)
  - SDK bridge proxy (`/sdk/*`)

- **genai_client.py** (68 lines) - Google Gemini API client
  - `edit_with_gemini_image()` - Main AI editing function

- **watcher.py** (330 lines) - Automated folder monitoring
  - Watches `input/` directory for new images
  - Auto-processes through AI pipeline
  - Archives originals after processing

### .NET Bridge

- **bridge-dotnet/NikonBridge/Program.cs** - HTTP server with endpoints:
  - `GET /status` - Camera connection state
  - `GET /live.mjpg` - MJPEG live view stream
  - `POST /shoot` - Capture image
  - `POST /sdk/connect` - Initialize and connect
  - `POST /sdk/disconnect` - Cleanup

- **bridge-dotnet/NikonMaidWrapper/** - C++/CLI wrapper
  - `NikonMaidWrapper.h` - Public interface
  - `NikonMaidWrapper.cpp` - MAID SDK integration

### Frontend

- **static/index.html** - Single-page web application
  - Style category selector
  - Preset buttons
  - File upload with camera capture
  - Live preview integration
  - Results gallery
  - iPad-friendly responsive design

### Configuration

- **config.json** - Application settings
  ```json
  {
    "input_dir": "input",
    "output_dir": "output",
    "archive_dir": "archive",
    "style_file": "styles\\background\\80s.txt",
    "editor_model": "gemini-2.5-flash-image",
    "mode": "background"
  }
  ```

- **.env** - API keys and environment variables
  - `GOOGLE_API_KEY` - Google AI Studio API key
  - `WATCH_DIR` - Folder watcher target
  - `BRIDGE_HOST`, `BRIDGE_PORT` - Camera bridge settings

## Current Implementation Status

### Working
- ✅ Web UI and FastAPI server fully functional
- ✅ AI image editing with Google Gemini
- ✅ Folder watcher for automated processing
- ✅ Style management system
- ✅ Custom prompt creation
- ✅ Bridge DLL loading and verification
- ✅ Basic HTTP server in .NET

### In Progress
- 🚧 Nikon MAID SDK initialization
- 🚧 Camera enumeration and connection
- 🚧 Live view frame capture and streaming
- 🚧 Real shutter trigger implementation

### Not Yet Implemented
- ❌ Error handling and auto-reconnect
- ❌ Camera settings control (ISO, aperture, etc.)
- ❌ Multiple camera support
- ❌ Advanced SDK features

## API Endpoints

### FastAPI Server (port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve web UI |
| GET | `/health` | Health check |
| GET | `/styles?category=...` | List style prompts |
| POST | `/edit` | Apply AI style to image |
| POST | `/prompts` | Create new style prompt |
| GET | `/watcher/status` | Folder watcher status |
| POST | `/watcher/start` | Start folder watcher |
| POST | `/watcher/stop` | Stop folder watcher |
| GET | `/watcher/logs` | View watcher logs |
| GET | `/config` | Get app configuration |
| POST | `/sdk/shoot` | Proxy to bridge for capture |
| GET | `/sdk/bridge` | Get bridge URL |

### .NET Bridge (port 9001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Camera connection state |
| GET | `/live.mjpg` | MJPEG live view stream |
| POST | `/shoot` | Capture image |
| POST | `/sdk/connect` | Initialize SDK and connect |
| POST | `/sdk/disconnect` | Cleanup and disconnect |
| POST | `/sdk/start-live` | Start live view |
| POST | `/sdk/stop-live` | Stop live view |

## Development Workflow

### Running the Application

1. **Start the .NET Bridge**
   ```bash
   cd bridge-dotnet/NikonBridge
   dotnet run
   ```
   Or open in Visual Studio 2022 and press F5

2. **Start the Python Server**
   ```bash
   python server.py
   ```
   Server runs on http://localhost:8000

3. **Access Web UI**
   Open browser to http://localhost:8000

### Camera Capture Workflow

1. User opens web UI and clicks "Start Camera"
2. UI calls `/sdk/connect` on FastAPI server
3. Server proxies to bridge at `http://localhost:9001/sdk/connect`
4. Bridge loads Nikon SDK DLLs and connects to Z6 II
5. User clicks "Capture" button
6. `/sdk/shoot` triggers shutter
7. Image downloads to `input/` directory
8. Folder watcher detects new file
9. Image processed through Gemini AI with selected style
10. Result saved to `output/` directory
11. Web UI displays result

## Technology Stack

### Backend
- Python 3.x with FastAPI
- .NET 8.0 with ASP.NET Core
- C++/CLI for native SDK wrapper

### AI/ML
- Google Gemini 2.5 Flash Image (AI Studio API)
- Google Imagen 3.0/4.0 (optional, requires Vertex AI)

### Image Processing
- SixLabors.ImageSharp (.NET)
- Pillow (Python)
- OpenCV (legacy prototype)

### Camera SDK
- Nikon MAID Type0029 module
- Target: Nikon Z6 II
- Protocol: USB with PTP

### Web
- Vanilla HTML/CSS/JavaScript
- MJPEG streaming (multipart/x-mixed-replace)
- HTML5 camera capture API

## Next Steps (SDK Integration)

Based on INSTRUCTIONS.md:

1. **Implement MAID initialization**
   - Call `MAIDEntryPointProc` with module path
   - Enumerate connected cameras
   - Open camera object

2. **Add live view methods**
   - `StartLive()` - Start live view mode
   - `StopLive()` - Stop live view mode
   - `GetLiveFrame()` - Capture frame buffer

3. **Wire MJPEG streaming**
   - Implement `/live.mjpg` endpoint
   - Continuous MJPEG stream from live view frames

4. **Implement real shutter trigger**
   - `Shoot()` method with object download callback
   - Save to WATCH_DIR

5. **Add robustness**
   - Error handling
   - Auto-reconnect on disconnection
   - Camera state management

## Documentation References

- **INSTRUCTIONS.md** - Comprehensive handoff document
- **docs/SDK_BRIDGE_PLAN.md** - Bridge architecture
- **docs/PHASE4_WEB_PLAN.md** - Web app design
- **S-SDKZ6_2-006BF-ALLIN/Module/Documents/English/** - Nikon SDK docs
  - MAID3(E).pdf - Core API reference
  - MAID3Type0029(E).pdf - Type0029 specifics
  - Usage of Type0029 Module(E).pdf - Integration guide
  - Type0029 Sample Guide(E).pdf - Sample code walkthrough

## Security Notes

- `.env` file contains exposed API key - should be secured
- PIN-based security available but optional
- CORS configured via `APP_ALLOW_ORIGINS`
- Local-first deployment recommended for events
- USB camera access requires Windows driver and exclusive access

## Dependencies

### Python (requirements.txt)
```
google-genai
Pillow
python-dotenv
watchdog
PySide6
fastapi
uvicorn
python-multipart
jinja2
opencv-python
```

### .NET (NikonBridge.csproj)
```
SixLabors.ImageSharp
DotNetEnv
```

### Native
- Nikon SDK DLLs (NkdPTP.dll, dnssd.dll, NkRoyalmile.dll, Type0029.md3)
- Visual C++ Runtime
- Windows USB drivers for Nikon Z6 II

## Git Status

- Current branch: master
- Recent work: Camera SDK integration, live view, prompt edits
- Untracked: INSTRUCTIONS.md, SDK ZIP, bridge-dotnet/, docs/

## Troubleshooting

### Bridge won't start
- Ensure Nikon SDK DLLs are in `bin/Debug/net8.0/` or `bin/x64/Debug/net8.0/`
- Check .env file exists with correct WATCH_DIR path
- Verify port 9001 is not in use

### Camera not detected
- Connect Z6 II via USB
- Ensure camera is powered on
- Check Windows Device Manager for USB devices
- Verify no other software is accessing camera

### AI editing fails
- Verify GOOGLE_API_KEY in .env
- Check network connectivity
- Review server.py logs for errors
- Ensure image format is supported (JPEG, PNG)

### Folder watcher not working
- Verify input directory exists and is writable
- Check watcher logs via `/watcher/logs` endpoint
- Ensure file permissions allow read/write

## Contact and Resources

- Project documentation: `docs/` directory
- Nikon SDK samples: `S-SDKZ6_2-006BF-ALLIN/Module/Win/Sample Program/`
- Google Gemini API: https://ai.google.dev/
