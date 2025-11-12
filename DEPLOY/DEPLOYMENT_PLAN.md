# AI Photo Booth - Deployment Package Plan

## Overview
This deployment package is designed to run on a laptop without requiring development tools like Visual Studio or full .NET SDK.

## Package Structure

```
AI_PhotoBooth/
├── camera_bridge/          # .NET camera control executable
│   ├── NikonBridge.exe    # Main executable
│   ├── NikonBridge.dll    # Main assembly
│   ├── NikonMaidWrapper.dll  # C++/CLI Nikon SDK wrapper
│   ├── *.dll              # All required .NET dependencies
│   └── .env               # Configuration (WATCH_DIR, ports)
│
├── sdk_dlls/              # Nikon SDK native DLLs
│   ├── Type0029.md3
│   ├── NkdPTP.dll
│   ├── dnssd.dll
│   └── NkRoyalmile.dll
│
├── python_server/         # Python FastAPI server
│   ├── server.py
│   ├── genai_client.py
│   ├── watcher.py
│   ├── config.json
│   ├── .env               # GOOGLE_API_KEY
│   ├── requirements.txt
│   └── static/           # Web UI
│       └── index.html
│
├── styles/                # AI prompt templates
│   ├── background/
│   └── retheme/
│
├── input/                 # Watch directory for new photos
├── output/                # AI-processed images
├── archive/               # Processed originals
│
├── START_PHOTOBOOTH.bat   # Main launcher
├── START_CAMERA.bat       # Camera bridge only
├── START_SERVER.bat       # Python server only
├── SETUP.bat              # First-time setup
└── README.md              # User instructions

```

## Deployment Options

### Option 1: Python with Requirements (Recommended for Development)
- Copy all Python files + requirements.txt
- User needs Python 3.x installed
- Run: `pip install -r requirements.txt`
- Pros: Easy to update, smaller package
- Cons: Requires Python installation

### Option 2: PyInstaller Standalone (Best for Events)
- Bundle Python server as single .exe
- No Python installation required
- Run: `pyinstaller --onefile server.py`
- Pros: No dependencies, double-click to run
- Cons: Larger file size (~50MB), harder to debug

### Option 3: Hybrid (Recommended)
- Provide both options
- Let user choose based on their setup

## Camera Bridge Deployment

The .NET bridge is **framework-dependent** (requires .NET 8.0 Runtime):
- Smaller deployment size
- User must install .NET 8.0 Runtime (free download)
- Include download link in setup script

Alternative: **Self-contained** deployment:
- Bundle .NET runtime with app (~80MB)
- No installation required
- Larger package size

## Launcher Scripts

### START_PHOTOBOOTH.bat
```batch
@echo off
echo Starting AI Photo Booth...
echo.

REM Start camera bridge in new window
start "Camera Bridge" cmd /c "cd camera_bridge && NikonBridge.exe"

REM Wait for bridge to initialize
timeout /t 3 /nobreak

REM Start Python server
cd python_server
python -m uvicorn server:app --host 0.0.0.0 --port 8000

pause
```

### SETUP.bat
```batch
@echo off
echo AI Photo Booth - First Time Setup
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.x from python.org
    pause
    exit /b 1
)

REM Check .NET Runtime
dotnet --list-runtimes | findstr "Microsoft.NETCore.App 8.0" >nul
if errorlevel 1 (
    echo WARNING: .NET 8.0 Runtime not found!
    echo Download from: https://dotnet.microsoft.com/download/dotnet/8.0
    echo.
)

REM Install Python dependencies
cd python_server
echo Installing Python dependencies...
pip install -r requirements.txt

REM Create .env template if needed
if not exist .env (
    echo Creating .env template...
    echo GOOGLE_API_KEY=your_api_key_here> .env
    echo WATCH_DIR=../input>> .env
)

echo.
echo Setup complete!
echo Edit python_server/.env to add your Google API key.
pause
```

## Required Files from Development Machine

### Camera Bridge (from `bridge-dotnet/NikonBridge/bin/x64/Debug/net8.0/`)
- NikonBridge.exe
- NikonBridge.dll
- NikonBridge.pdb (optional, for debugging)
- NikonMaidWrapper.dll
- NikonMaidWrapper.pdb (optional)
- All .NET dependency DLLs (SixLabors.ImageSharp.dll, etc.)
- appsettings.json (if exists)

### SDK DLLs (from `S-SDKZ6_2-006BF-ALLIN/Module/Win/Bin/x64/`)
- Type0029.md3
- NkdPTP.dll
- dnssd.dll
- NkRoyalmile.dll

### Python Server
- server.py
- genai_client.py
- watcher.py
- config.json
- requirements.txt
- static/ (entire directory)
- styles/ (entire directory)

## Configuration Files

### camera_bridge/.env
```
WATCH_DIR=C:\path\to\AI_PhotoBooth\input
BRIDGE_PORT=9001
```

### python_server/.env
```
GOOGLE_API_KEY=your_actual_api_key
WATCH_DIR=../input
BRIDGE_HOST=http://localhost
BRIDGE_PORT=9001
```

### python_server/config.json
```json
{
  "input_dir": "../input",
  "output_dir": "../output",
  "archive_dir": "../archive",
  "style_file": "../styles/background/80s.txt",
  "editor_model": "gemini-2.5-flash-image",
  "mode": "background"
}
```

## User Setup Instructions (README.md)

1. **Prerequisites**
   - Python 3.10 or higher
   - .NET 8.0 Runtime
   - Google AI Studio API Key
   - Nikon Z6 II camera connected via USB

2. **First-Time Setup**
   - Run `SETUP.bat`
   - Edit `python_server/.env` and add your Google API key

3. **Running the App**
   - Connect Nikon Z6 II via USB
   - Run `START_PHOTOBOOTH.bat`
   - Open browser to `http://localhost:8000`

4. **Troubleshooting**
   - If camera not detected: Check USB connection, ensure no other software is using camera
   - If web UI not loading: Check that port 8000 is not in use
   - If bridge fails: Ensure .NET 8.0 Runtime is installed

## Next Steps

1. ✅ Create deployment folder structure
2. ⬜ Copy camera bridge files from working build
3. ⬜ Copy SDK DLLs
4. ⬜ Copy Python server files
5. ⬜ Create launcher scripts (.bat files)
6. ⬜ Create user README.md
7. ⬜ Test on clean machine (or at least in different directory)
8. ⬜ Create ZIP package for easy transfer

## Transfer to Laptop

Once packaged:
1. Create `AI_PhotoBooth.zip`
2. Transfer via USB drive, network share, or cloud storage
3. Extract on laptop
4. Run `SETUP.bat`
5. Configure API key
6. Run `START_PHOTOBOOTH.bat`

## File Size Estimates

- Camera Bridge: ~5-10 MB (.NET deps)
- SDK DLLs: ~2-3 MB
- Python Files: <1 MB
- Python Dependencies (venv): ~100-200 MB
- **Total: ~110-220 MB** (excluding Python installation)

With PyInstaller standalone:
- **Total: ~150-300 MB**
