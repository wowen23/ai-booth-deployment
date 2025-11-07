# AIBooth Bridge + Nikon SDK Handoff

This document summarizes what is working now, how to run it, and the exact next steps to wire the Nikon SDK (MAID Type0029) for live view + shutter.

## What is working now
- Web app (FastAPI + UI) is functional.
- Python bridge prototype (OpenCV) exists but is being superseded by the .NET bridge.
- .NET bridge scaffold (NikonBridge, net8.0) with endpoints:
  - GET /status → shows watch_dir, DLL detect results, connected/live flags.
  - POST /sdk/connect → wired to the C++/CLI wrapper; currently loads Nikon runtime DLLs and verifies Type0029.md3 presence.
  - POST /sdk/start-live → scaffolded (returns ok), streaming not yet wired.
  - POST /sdk/stop-live → scaffolded.
  - POST /sdk/disconnect → unloads DLLs via wrapper.
  - GET /live.mjpg → returns 501 (Not Implemented) until SDK live frames are wired.
  - POST /shoot → currently writes a stub JPEG into WATCH_DIR for end-to-end testing.
- Environment loading in NikonBridge:
  - Uses .env via DotNetEnv. You can set:
    - WATCH_DIR=C:\Users\willi\image_gen\input
    - BRIDGE_PORT=9001
- Visual Studio solution setup:
  - C# NikonBridge (Startup Project) references C++/CLI NikonMaidWrapper.
  - C++/CLI project outputs its DLL next to NikonBridge.exe (bin\Debug\net8.0).
  - Build configuration: Debug | x64.

## Files and paths
- Root: C:\Users\willi\image_gen
- Bridge (C#): bridge-dotnet\NikonBridge\
  - Program.cs: endpoints and env loading.
  - .env: stores WATCH_DIR, BRIDGE_PORT.
- Wrapper (C++/CLI): bridge-dotnet\NikonMaidWrapper\
  - NikonMaidWrapper.h/.cpp: public API (MaidBridge) and DLL loading.
- Nikon SDK binaries (must be next to NikonBridge.exe):
  - C:\Users\willi\image_gen\bridge-dotnet\NikonBridge\bin\Debug\net8.0\
    - Type0029.md3
    - NkdPTP.dll
    - dnssd.dll
    - NkRoyalmile.dll

## How to run (Visual Studio)
1) Open the solution:
   - Open NikonMaidWrapper.sln (or the combined solution if you created one) in Visual Studio 2022.
   - Ensure both projects are visible (NikonMaidWrapper + NikonBridge).
2) Set build config:
   - Debug | x64 for both projects (Configuration Manager).
3) Ensure env:
   - NikonBridge\.env has:
     - WATCH_DIR=C:\\Users\\willi\\image_gen\\input
     - BRIDGE_PORT=9001
4) Place Nikon SDK binaries into:
   - C:\\Users\\willi\\image_gen\\bridge-dotnet\\NikonBridge\\bin\\Debug\\net8.0\\
   - Files: Type0029.md3, NkdPTP.dll, dnssd.dll, NkRoyalmile.dll
5) Build + Run:
   - Set NikonBridge as Startup Project → F5.
6) Test endpoints (PowerShell):
   - Status:
     - irm http://localhost:9001/status
   - Connect (loads DLLs and checks md3):
     - irm http://localhost:9001/sdk/connect -Method POST
   - Start live (scaffold):
     - irm http://localhost:9001/sdk/start-live -Method POST
   - Live stream (501 until wired):
     - irm http://localhost:9001/live.mjpg
   - Shoot (stub):
     - irm http://localhost:9001/shoot -Method POST

## Troubleshooting
- dotnet run from normal PowerShell fails building vcxproj:
  - Use Visual Studio (F5) or Developer PowerShell for VS 2022.
- Wrong watch_dir when launching from VS:
  - Ensure .env exists (exactly `.env`, not `.env.txt`).
- 405 Method Not Allowed on /sdk/connect:
  - Use POST (control routes are POST).
- 500 on /sdk/connect:
  - Check that Type0029.md3 and the 3 DLLs are present next to the EXE.
  - Ensure no other app (Webcam Utility, NX Tether, Camera app) has the camera.
- C++/CLI build issues:
  - Platform: x64.
  - /clr enabled; /EHa (SEH exceptions); Debug Info: /Zi; Basic runtime checks disabled.
  - Install: Desktop development with C++ and C++/CLI support.

## EXACT next steps to complete SDK integration
1) Wrapper: MAID initialize + open camera (current task)
   - Load Type0029.md3 with MAID API.
   - Initialize library, enumerate/select Z6 II, open device.
   - Return connected=true only after success.
2) Wrapper: StartLive/StopLive + GetLiveFrame
   - Start Nikon SDK Live View.
   - Fetch frames, produce JPEG buffers.
   - Provide those via GetLiveFrame().
3) Bridge: Implement /live.mjpg
   - Stream multipart/x-mixed-replace MJPEG using GetLiveFrame() in a loop.
   - Handle cancellation and client disconnects.
4) Wrapper: Shoot
   - Trigger shutter; handle object-added/download callback.
   - Save JPEG(s) into WATCH_DIR; return filenames.
5) Robustness
   - Exclusive access errors → 409/423 with clear message.
   - Auto-reconnect on camera disconnect.
   - Optional: camera settings endpoints (ISO, shutter, AF).

## What you can do in parallel
- Confirm the Nikon sample (optional): build the Type0029 sample in SDK to validate camera and drivers on your machine.
- Keep the 4 Nikon binaries next to NikonBridge.exe after each build.
- Ensure the camera is not in use by Webcam Utility/NX Tether when testing connect/live.

## Contact points
- If /status shows wrong watch_dir, check `.env` and restart.
- If /sdk/connect 500s, verify files and exclusive USB.
- If dotnet CLI fails to build, run from Visual Studio or Developer PowerShell.

---
This document should make it easy to run what’s here and see exactly what’s left to wire. Once MAID connect is committed, we’ll move quickly to Live View streaming and Shoot.
