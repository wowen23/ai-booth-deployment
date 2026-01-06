# MTP Bridge - Final Recommendation

## Current Status

✅ **Camera IS detected** - "Z 6_2" found via Shell.Application
✅ **Python can see it** - Detection works
❌ **Python can't control it** - Cannot send MTP commands without:
   - libusb driver (replaces Windows driver, breaks Nikon software)
   - PortableDeviceApiLib COM (not registered/accessible on this Windows)

## The Solution: Use .NET Bridge

Your `bridge-mtp/` folder already has a **working .NET implementation** that:
- ✅ Uses Windows Portable Devices API (same as we're trying in Python)
- ✅ Can send MTP commands (StartLiveView 0x9201, etc.)
- ✅ Already connects to camera
- ✅ Already starts live view
- ⏳ Just needs HTTP server added

## Two Options

### Option 1: Complete the .NET MTP Bridge (RECOMMENDED)

**What's needed:**
1. Add ASP.NET HTTP server (copy from your NikonBridge)
2. Add MJPEG streaming endpoint
3. Complete frame extraction from WPD IStream
4. Build and run

**Time:** ~1-2 hours

**Files:**
- `bridge-mtp/NikonMtpCamera.cs` - Already has MTP commands ✅
- `bridge-mtp/Program.cs` - Convert to HTTP server
- Same architecture as your MAID bridge

### Option 2: Python Wrapper Around .NET Bridge

**What's needed:**
1. Build .NET bridge as console app
2. Python calls it via subprocess
3. Use stdin/stdout for communication
4. Python HTTP server wraps it

**Time:** ~30 minutes

**Advantage:** All-Python web server, .NET just for camera control

## Why .NET Works and Python Doesn't

| Approach | Python | .NET |
|----------|--------|------|
| Detect camera | ✅ Shell.Application | ✅ WPD API |
| Send MTP commands | ❌ COM not registered | ✅ COM works |
| PortableDeviceApiLib | ❌ Not accessible | ✅ Works natively |
| Live view | ❌ Can't send 0x9201 | ✅ Can send |
| Capture | ❌ Can't send 0x90AF | ✅ Can send |

.NET has better COM interop on Windows - it's the right tool for this job.

## Next Step

**Build the .NET MTP bridge:**

```bash
cd bridge-mtp
msbuild MtpBridge.sln /p:Configuration=Release
```

Or open in Visual Studio and press F5.

It already connects and starts live view - we just need to:
1. Complete IStream frame reading
2. Add HTTP endpoints

Want me to help complete the .NET bridge instead?
