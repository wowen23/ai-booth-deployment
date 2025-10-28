import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env BEFORE reading any env vars
load_dotenv()

# Config via env
BRIDGE_HOST = os.getenv("BRIDGE_HOST", "0.0.0.0")
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "9001"))
CAM_INDEX = int(os.getenv("BRIDGE_CAM_INDEX", "0"))
WATCH_DIR = os.getenv("WATCH_DIR") or os.getenv("BRIDGE_WATCH_DIR") or "output"
FPS = int(os.getenv("BRIDGE_FPS", "15"))

app = FastAPI(title="Nikon SDK Bridge (Prototype)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_watch_dir = (Path(WATCH_DIR)).resolve()
_watch_dir.mkdir(parents=True, exist_ok=True)

_cap_lock = threading.Lock()
_cap: Optional[cv2.VideoCapture] = None
_last_frame_lock = threading.Lock()
_last_frame: Optional[bytes] = None
_run_flag = False
_worker_thread: Optional[threading.Thread] = None


def _open_camera() -> cv2.VideoCapture:
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
    # Prefer 1920x1080 if available
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_FPS, 30)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open camera index {CAM_INDEX}")
    return cap


def _reader_loop():
    global _cap, _last_frame, _run_flag
    interval = 1.0 / max(1, FPS)
    while _run_flag:
        with _cap_lock:
            cap = _cap
        if cap is None:
            time.sleep(0.2)
            continue
        ok, frame = cap.read()
        if not ok or frame is None:
            time.sleep(0.05)
            continue
        ok, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if ok:
            with _last_frame_lock:
                _last_frame = jpg.tobytes()
        time.sleep(interval)


def _ensure_running():
    global _cap, _run_flag, _worker_thread
    with _cap_lock:
        if _cap is None:
            _cap = _open_camera()
    if not _run_flag:
        _run_flag = True
        t = threading.Thread(target=_reader_loop, daemon=True)
        _worker_thread = t
        t.start()


@app.get("/status")
def status():
    with _cap_lock:
        opened = _cap.isOpened() if _cap is not None else False
    return {
        "camera_index": CAM_INDEX,
        "opened": opened,
        "watch_dir": str(_watch_dir),
        "fps": FPS,
    }


@app.get("/live.mjpg")
def live_mjpg():
    _ensure_running()

    def gen():
        boundary = "frame"
        while True:
            with _last_frame_lock:
                data = _last_frame
            if data is None:
                time.sleep(0.02)
                continue
            yield (b"--" + boundary.encode() + b"\r\n"
                   b"Content-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
            time.sleep(1.0 / max(1, FPS))

    return StreamingResponse(gen(), media_type='multipart/x-mixed-replace; boundary=frame')


@app.post("/shoot")
def shoot():
    _ensure_running()
    # Use the most recent frame as the capture; wait briefly if not ready yet
    data = None
    deadline = time.time() + 2.0
    while time.time() < deadline and data is None:
        with _last_frame_lock:
            data = _last_frame
        if data is None:
            time.sleep(0.05)
    if data is None:
        # As a fallback, try to grab a frame directly once
        with _cap_lock:
            cap = _cap
        if cap is not None:
            ok, frame = cap.read()
            if ok and frame is not None:
                ok2, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if ok2:
                    data = jpg.tobytes()
    if not data:
        raise HTTPException(status_code=503, detail="No frame available yet (timeout)")
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f"sdk_capture_{ts}.jpg"
    out_path = _watch_dir / name
    try:
        out_path.write_bytes(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save: {e}")
    return JSONResponse({"ok": True, "file": str(out_path)})


@app.on_event("shutdown")
def on_shutdown():
    global _cap, _run_flag
    _run_flag = False
    with _cap_lock:
        if _cap is not None:
            try:
                _cap.release()
            except Exception:
                pass
            _cap = None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=BRIDGE_HOST, port=BRIDGE_PORT)
