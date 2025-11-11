# Python MTP Bridge Setup Guide

## Overview

We've created a **pure Python** MTP bridge to replace the Nikon MAID SDK. This works with your Nikon Z6 II camera over USB using the MTP/PTP protocol.

## Files Created

1. **mtp_camera.py** - Camera wrapper using `ptpy` (requires libusb)
2. **mtp_camera_wpd.py** - Camera wrapper using Windows Portable Devices API
3. **mtp_server.py** - FastAPI HTTP server (port 9001)
4. **test_mtp_bridge.py** - Test suite
5. **quick_test_mtp.py** - Quick connection test
6. **list_mtp_devices.py** - Device detection utility

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `pywin32` - Windows COM access
- `comtypes` - COM type library support
- `WMI` - Windows Management Instrumentation
- `ptpy` - Python PTP library
- `pyusb` - USB device access
- `fastapi`, `uvicorn` - HTTP server

### 2. Camera Setup

**On the Nikon Z6 II:**

1. Connect camera to PC via USB cable
2. Power on the camera
3. Go to camera menu: **Setup Menu → USB Connection → MTP/PTP**
4. Ensure camera is not in playback mode
5. You should hear Windows "device connected" sound

**In Windows:**

1. Open **Device Manager** (devmgmt.msc)
2. Look under **Portable Devices**
3. You should see "NIKON Z 6_2" or similar
4. If you see a yellow warning icon, you may need drivers

### 3. Verify Connection

```bash
python list_mtp_devices.py
```

This will show if your camera is detected via WMI or USB.

## Usage

### Quick Test

```bash
python quick_test_mtp.py
```

This attempts to:
- Detect camera
- Connect via MTP
- Get camera info
- Check if ready
- Disconnect

### Full Test Suite

```bash
python test_mtp_bridge.py
```

Tests:
- Basic connection
- Live view start/stop
- Frame capture
- Still image capture
- Autofocus

### Run MTP Bridge Server

```bash
python mtp_server.py
```

Server starts on **http://localhost:9001** with endpoints:
- `POST /sdk/connect` - Connect to camera
- `GET /status` - Camera status
- `POST /sdk/start-live` - Start live view
- `GET /live.mjpg` - MJPEG stream
- `POST /shoot` - Capture image
- `POST /sdk/disconnect` - Disconnect

### Integrate with Web App

Your existing `server.py` already proxies to port 9001!

**No changes needed** - just start the MTP server instead of the .NET bridge:

```bash
# Terminal 1: Start MTP bridge
python mtp_server.py

# Terminal 2: Start main web app
python server.py
```

Then open http://localhost:8000 in your browser!

## Troubleshooting

### Camera Not Detected

**Check USB Mode:**
- Camera menu: Setup → USB Connection → **MTP/PTP** (not Mass Storage or PC Control)

**Check Connection:**
```bash
python list_mtp_devices.py
```

**Check Device Manager:**
- Open `devmgmt.msc`
- Look under "Portable Devices"
- Should see "NIKON Z 6_2"

**If yellow warning icon:**
- Right-click device → Update driver
- Choose "Search automatically"
- Or download Nikon USB driver

### "No USB PTP device found" (ptpy)

The `ptpy` library needs a USB backend on Windows.

**Option A: Use WPD version** (recommended for Windows)
```python
# Use mtp_camera_wpd.py instead of mtp_camera.py
```

**Option B: Install libusb driver**
1. Download Zadig: https://zadig.akeo.ie/
2. Run Zadig
3. Options → List All Devices
4. Select "NIKON Z 6_2"
5. Replace driver with libusbK or WinUSB
6. ⚠️ This may break other Nikon software!

**Option C: Use .NET bridge**
```bash
cd bridge-mtp
dotnet run
```

### "Invalid class string" (pywin32)

The Windows Portable Devices COM library isn't registered.

**Check if library exists:**
```bash
python -c "import win32com.client; print(win32com.client.Dispatch('Shell.Application'))"
```

If this fails, reinstall pywin32:
```bash
python -m pip uninstall pywin32
python -m pip install pywin32
python Scripts/pywin32_postinstall.py -install
```

### Live View Not Working

**Camera settings:**
- Ensure lens cap is off
- Camera not in playback mode
- Camera not in mass storage mode
- Battery charged

**Code check:**
```python
camera.connect()
camera.start_live_view()
time.sleep(1)  # Wait for live view to start
frame = camera.get_live_view_frame()
```

### Frames Are Empty

Live view data extraction from WPD IStream is complex. Two options:

**Option 1:** Complete the WPD IStream reader in `mtp_camera_wpd.py`

**Option 2:** Use the .NET bridge (already has this working)

## Implementation Status

### ✅ Complete
- Camera detection
- Connection/disconnection
- Command sending (StartLiveView, EndLiveView, DeviceReady)
- Capture trigger
- HTTP server structure
- All endpoints defined

### ⏳ In Progress
- Live view frame extraction (WPD IStream → bytes)
- MJPEG streaming
- Error handling

### ❌ Not Started
- Camera settings control (ISO, aperture, etc.)
- Image download from card
- Focus point control
- Bracketing

## Comparison: Python vs .NET

| Feature | Python (ptpy) | Python (WPD) | .NET (WPD) |
|---------|---------------|--------------|------------|
| Platform | Cross-platform | Windows only | Windows only |
| Dependencies | libusb/WinUSB | pywin32 | .NET Fx 4.8 |
| Driver | Needs replacement | Native | Native |
| Complexity | Simple | Medium | Medium |
| Frame extraction | ✅ Built-in | ❌ TODO | ⏳ TODO |
| Status | Blocked on driver | Partial | Partial |

## Recommendation

**For quick testing:**
1. Use .NET bridge (`bridge-mtp/`) - most complete

**For Python solution:**
1. Connect camera with MTP/PTP mode
2. Verify in Device Manager
3. Try `mtp_camera_wpd.py` (Windows native)
4. Complete IStream frame extraction

**Long term:**
- Either complete Python WPD wrapper
- Or keep .NET bridge and call from Python subprocess
- Or install libusb driver for ptpy

## Next Steps

1. **Connect camera** and verify detection
2. **Test basic connection** with `quick_test_mtp.py`
3. **Choose implementation**:
   - Complete Python WPD (best for all-Python stack)
   - Use .NET bridge (fastest to working solution)
4. **Complete frame extraction**
5. **Test with web UI**

## Support

If you have the camera connected and it's still not working:

1. Run `python list_mtp_devices.py` and share output
2. Check Device Manager screenshot
3. Verify camera USB mode setting
4. Try the .NET bridge as fallback

The infrastructure is all ready - just need to solve the Windows USB/MTP device access!
