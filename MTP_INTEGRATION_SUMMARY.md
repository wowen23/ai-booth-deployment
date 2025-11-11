# MTP Camera Bridge Integration Summary

## What We Built

Created a **drop-in replacement** for the Nikon MAID SDK bridge using the **MTP/PTP protocol** instead.

### Why MTP?

The MAID SDK has a critical limitation with mirrorless cameras:
- Mirrorless Z6 II is always in "Camera Live View" mode (status=4)
- MAID `GetLiveViewImage` requires "Remote Live View" mode (status=3)
- Cannot switch modes → live view buffer stays empty

**MTP solves this** with direct commands designed for remote camera control.

---

## Two Implementation Approaches

### Option 1: Python MTP Bridge (ptpy) ⚠️ **Has USB driver issue on Windows**

**Files created:**
- `mtp_camera.py` - Core camera wrapper using ptpy library
- `mtp_server.py` - FastAPI HTTP server
- `test_mtp_bridge.py` - Test suite
- `quick_test_mtp.py` - Quick connection test
- `MTP_BRIDGE_README.md` - Full documentation

**Status:** ✅ Code complete, ❌ Requires libusb driver on Windows

**Issue:** `ptpy` uses `pyusb` which needs libusb/WinUSB driver installation. Windows MTP cameras use WPD driver instead.

**To fix:** Would need to install Zadig and replace camera driver (not ideal).

---

### Option 2: .NET Framework MTP Bridge (WPD) ✅ **RECOMMENDED**

**Files:**
- `bridge-mtp/NikonMtpCamera.cs` - Windows Portable Devices wrapper
- `bridge-mtp/Program.cs` - Test console app
- `bridge-mtp/WpdInterop.cs` - COM interop helpers

**Status:** ⏳ Core MTP commands working, needs HTTP server + frame extraction

**Advantages:**
- Uses native Windows WPD API (PortableDeviceApiLib COM)
- No driver installation needed
- Already tested and connecting to camera
- Same architecture as your MAID bridge

**What's working:**
- ✅ Device enumeration
- ✅ Connection (`Open()`)
- ✅ `StartLiveView` command
- ✅ `EndLiveView` command
- ✅ `DeviceReady` polling

**What needs completion:**
1. Fix `GetLiveViewFrame()` - extract byte[] from WPD stream
2. Add ASP.NET HTTP server (like NikonBridge)
3. Add MJPEG streaming endpoint
4. Add capture endpoint

---

## Recommended Next Steps

### Complete .NET MTP Bridge (.NET Framework 4.8)

This is the path of least resistance for Windows:

1. **Fix frame extraction in `GetLiveViewFrame()`**
   ```csharp
   // Current code gets IUnknown transfer context
   // Need to: Read IStream → byte[] → find JPEG marker → return
   ```

2. **Add HTTP server**
   - Copy ASP.NET setup from `bridge-dotnet/NikonBridge/Program.cs`
   - Create endpoints: `/status`, `/sdk/connect`, `/shoot`, `/live.mjpg`
   - Use same port 9001

3. **Test with camera**
   - Build and run
   - Verify live view frames
   - Test MJPEG stream

4. **Integration**
   - Your existing web app already proxies to port 9001
   - No changes needed!

---

## MTP Operation Codes (from Z6_2UsbMtp.txt)

```csharp
const ushort OP_StartLiveView = 0x9201;
const ushort OP_EndLiveView = 0x9202;
const ushort OP_GetLiveViewImage = 0x9203;
const ushort OP_GetLiveViewImageEx = 0x9428;  // Returns JPEG
const ushort OP_DeviceReady = 0x90A2;
const ushort OP_InitiateCaptureRecInMedia = 0x90AF;  // Shutter
const ushort OP_AFDrive = 0x90C1;  // Autofocus
const ushort OP_OpenSession = 0x1002;
const ushort OP_CloseSession = 0x1003;
```

---

## Live View Data Format

According to `Z6_2UsbMtp.txt` section 9.7:

```
[Version Header]  ← Variable length
[JPEG Image Data] ← Starts with 0xFFD8
```

**Extraction logic:**
1. Get data from WPD transfer context (IStream)
2. Find JPEG start marker (0xFFD8)
3. Extract from marker to end
4. Return as byte[]

---

## Architecture (Final)

```
[Nikon Z6 II Camera]
        ↓ USB (MTP/PTP)
[.NET Framework 4.8 Bridge] ← Windows Portable Devices API
        ↓ HTTP (port 9001)
[Python FastAPI Server] (server.py)
        ↓ HTTP/WebSocket
[Web UI]
```

**Same architecture as before, just swap MAID for MTP!**

---

## API Endpoints (Target)

Match your existing MAID bridge exactly:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Camera connection status |
| `/sdk/connect` | POST | Connect to camera via MTP |
| `/sdk/disconnect` | POST | Disconnect |
| `/sdk/start-live` | POST | Start live view mode |
| `/sdk/stop-live` | POST | Stop live view mode |
| `/live.mjpg` | GET | MJPEG stream |
| `/shoot` | POST | Trigger shutter |

**No changes needed in:**
- `server.py` (already proxies to port 9001)
- `static/index.html` (already calls these endpoints)

---

## Testing Checklist

- [ ] Build .NET Framework project
- [ ] Run console app to test MTP connection
- [ ] Verify `StartLiveView` works
- [ ] Fix `GetLiveViewFrame` data extraction
- [ ] Test JPEG extraction
- [ ] Add HTTP server
- [ ] Test `/live.mjpg` endpoint
- [ ] Test `/shoot` endpoint
- [ ] Integrate with web UI
- [ ] Test full photo booth workflow

---

## Files Summary

### Python Approach (has driver issue)
```
mtp_camera.py           - Camera wrapper (ptpy)
mtp_server.py           - HTTP server
test_mtp_bridge.py      - Test suite
quick_test_mtp.py       - Quick test
MTP_BRIDGE_README.md    - Documentation
```

### .NET Approach (recommended)
```
bridge-mtp/
├── NikonMtpCamera.cs       - WPD camera wrapper ✅
├── Program.cs              - Test console app ✅
├── WpdInterop.cs           - COM helpers ✅
├── MtpBridge.NetFx.csproj  - Project file
└── [TODO] HttpServer.cs    - ASP.NET endpoints
```

---

## Key Insights

1. **MTP is the right protocol** - Z6_2UsbMtp.txt confirms this is the intended way
2. **Windows WPD works best** - Native API, no driver issues
3. **Drop-in replacement** - Same HTTP endpoints as MAID bridge
4. **Already 80% done** - Your .NET code already connects and sends commands!

---

## Next Action

**Recommend:** Complete the .NET Framework MTP bridge

**Priority tasks:**
1. Fix `GetLiveViewFrame()` data extraction
2. Add simple HTTP server (copy from NikonBridge)
3. Test with camera
4. Deploy!

The Python approach is a nice fallback for cross-platform needs, but for Windows-only deployment (photo booth), .NET Framework + WPD is the fastest path.

---

## References

- `docs/Z6_2UsbMtp.txt` - Complete MTP specification (624KB)
- `bridge-mtp/MTP_RESEARCH.md` - Your research notes
- `bridge-mtp/NEXT_STEPS.md` - Analysis of options

---

**Ready to complete the .NET MTP bridge?** The foundation is already there! 🚀
