# Archived Documentation

This folder contains documentation for **abandoned approaches** that were explored during development but ultimately not used in the final implementation.

## Why These Are Archived

### MTP (Media Transfer Protocol) Approach - NOT USED

**Files:**
- `MTP_BRIDGE_README.md`
- `MTP_INTEGRATION_SUMMARY.md`
- `MTP_PYTHON_COMPLETE.md`
- `PYTHON_MTP_SETUP.md`
- `RECOMMENDATION.md`

**What was tried:**
We initially attempted to control the Nikon Z6 II camera using Windows MTP (Media Transfer Protocol) via Python's COM interfaces. This would have been simpler than using the Nikon MAID SDK.

**Why it didn't work:**
- Python's `win32com` couldn't access the required `PortableDeviceApiLib` COM interfaces on this Windows installation
- MTP approach would have required `libusb` driver replacement, which breaks Nikon's official software
- .NET has better COM interop but still faced limitations with MTP commands

**Final decision:**
Switched to the **Nikon MAID SDK** (Type0029 module) which provides:
- Official support for Z6 II via USB PTP protocol
- Full control of camera settings
- Reliable live view streaming
- Professional-grade capture and download

## Current Implementation

**What we're using:**
- **Nikon MAID SDK Type0029** via C++/CLI wrapper
- **C++/CLI NikonMaidWrapper** exposes SDK to .NET
- **.NET 8 ASP.NET Core bridge** provides HTTP API
- **Python FastAPI server** handles web UI and AI processing

See `../SDK_BRIDGE_PLAN.md` and `../START_HERE.md` for current architecture.

## Lessons Learned

1. **Native SDK > Protocol Hacking** - Official SDKs are more reliable than reverse-engineering protocols
2. **C++/CLI is valuable** - Bridging native C++ code to .NET is easier than Python ctypes
3. **Windows COM is painful** - COM interface availability varies by Windows installation
4. **Prototype quickly, pivot faster** - We tried MTP for 2 hours, recognized the blocker, and switched

---

**Status:** These documents are kept for historical reference only. Do not attempt to implement MTP approach.
