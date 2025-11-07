# Nikon SDK Bridge Plan

## Goal
Replace the OpenCV prototype bridge with a Nikon SDK–backed local bridge on Windows that provides:
- USB Live View stream (served as MJPEG at `/live.mjpg`).
- Shutter trigger endpoint `/shoot` that downloads JPEG(s) into the server's `WATCH_DIR` so the existing watcher processes and publishes results automatically.

## Architecture
- Keep the current FastAPI server and web UI unchanged.
- Add a small local Windows app (the "bridge") that:
  - Owns the camera USB connection (exclusive access).
  - Starts/stops Live View and exposes a local HTTP API.
  - Saves captured files to `WATCH_DIR`.
- The web UI talks to the bridge via the existing proxy endpoints:
  - `GET /sdk/bridge` (server → returns bridge URL)
  - `POST /sdk/shoot` (server → forwards to bridge `/shoot`)
  - UI shows MJPEG directly from `http://<bridge>/live.mjpg`.

## Endpoints (Bridge)
- `GET /status`
  - Returns camera connection state, live view status, selected device, `watch_dir`.
- `GET /live.mjpg`
  - Streams frames from Nikon SDK Live View as multipart MJPEG (`multipart/x-mixed-replace`).
- `POST /shoot`
  - Triggers capture via SDK, downloads JPEG to `WATCH_DIR`, returns `{ ok: true, files: ["<abs path>"] }`.
- Optional
  - `POST /connect`, `POST /disconnect` to explicitly manage device.
  - `POST /settings` to adjust ISO/shutter/AF mode where supported.

## Configuration
- Read from `.env` or appsettings:
  - `WATCH_DIR` → destination folder (should match server watcher / config.json input_dir for immediate processing).
  - `BRIDGE_HOST` (default `0.0.0.0`), `BRIDGE_PORT` (default `9001`).
  - `BRIDGE_FPS` for Live View target frame rate.
  - `CAMERA_SELECTION` (if multiple devices; optional).

## Implementation details
- Language: C# (.NET 8) recommended for rapid HTTP hosting and SDK interop; C++ is also viable.
- SDK integration:
  - Initialize SDK, list devices, open Z6 II.
  - Start Live View; receive frames; encode to JPEG if needed; stream as MJPEG.
  - On `/shoot`, trigger shutter; receive/download file to `WATCH_DIR`.
- Error handling:
  - Exclusive access errors → return 423/409 with a clear message.
  - Device disconnects → auto-retry; expose via `/status`.
- Packaging:
  - Bundle Nikon DLLs; produce a single folder or installer.
  - Optional tray app or Windows Service.

## Web UI polish (post-bridge)
- Show filename returned by `/sdk/shoot` and link to processed result after watcher finishes.
- Option to auto-open Live View on page load.

## Milestones
1. Prototype bridge with Nikon SDK: `/live.mjpg`, `/shoot`, saves to `WATCH_DIR`.
2. Robustness: auto-reconnect, error messages, device selection.
3. Packaging: EXE + DLLs; optional service/tray.
4. Optional: camera settings API.

## Notes
- USB is exclusive: when the SDK bridge owns the camera, Nikon Webcam Utility and NX Tether cannot use it simultaneously.
- For simultaneous live view (HDMI) + stills (USB SDK), use an HDMI capture card for the browser preview and SDK over USB for capture.
