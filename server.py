import os
import json
import time
import threading
from collections import deque
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from genai_client import edit_with_gemini_image
from qr_generator import generate_photo_qr, get_qr_code_base64
from email_sender import send_photo_email, validate_email

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STYLES_DIR = BASE_DIR / "styles"
STATIC_DIR = BASE_DIR / "static"
GALLERY_DB = BASE_DIR / "galleries.json"

load_dotenv()

app = FastAPI(title="AI Booth Web")

# CORS: read allowed origins from env (comma-separated); default to localhost only
allow_origins_env = os.getenv("APP_ALLOW_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
allow_origins = [o.strip() for o in allow_origins_env if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Defaults if missing
    return {
        "output_dir": "output",
        "editor_model": "gemini-2.5-flash-image",
    }


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    # Serve the static index.html
    idx = STATIC_DIR / "index.html"
    if not idx.exists():
        return HTMLResponse("<h1>AI Booth Web</h1><p>Static UI missing.</p>")
    return HTMLResponse(idx.read_text(encoding="utf-8"))


@app.get("/styles")
def get_styles(category: str = "background"):
    cat_dir = STYLES_DIR / category
    if not cat_dir.exists():
        return {"category": category, "styles": []}
    items = []
    for p in sorted(cat_dir.glob("*.txt")):
        items.append({
            "name": p.stem,
            "path": str(p.relative_to(BASE_DIR)).replace("\\", "/"),
        })
    return {"category": category, "styles": items}


class EditResponse(BaseModel):
    id: str
    files: List[str]
    qr_code_url: str = ""
    gallery_url: str = ""


@app.post("/edit", response_model=EditResponse)
async def edit_image(
    file: UploadFile = File(...),
    style_path: str = Form(...),
    editor_model: str = Form("gemini-2.5-flash-image"),
    pin: str | None = Form(None),
):
    # PIN gate (optional): if APP_PIN is set, require matching pin
    app_pin = os.getenv("APP_PIN")
    if app_pin:
        if not pin or pin != app_pin:
            raise HTTPException(status_code=401, detail="Invalid PIN")
    # Read style prompt
    style_abs = (BASE_DIR / style_path).resolve()
    if not style_abs.exists() or not style_abs.is_file():
        raise HTTPException(status_code=400, detail="Invalid style_path")
    prompt_text = style_abs.read_text(encoding="utf-8").strip()

    # Read image bytes
    try:
        img_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")

    # Call Gemini edit
    try:
        images = edit_with_gemini_image(img_bytes, prompt_text, model=editor_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {e}")
    if not images:
        raise HTTPException(status_code=500, detail="No images returned")

    # Save outputs
    cfg = load_config()
    output_dir = (BASE_DIR / cfg.get("output_dir", "output")).resolve()
    ensure_dir(output_dir)

    ts = time.strftime("%Y%m%d_%H%M%S")
    job_id = f"{ts}"
    saved_urls: List[str] = []

    stem = Path(file.filename or "upload").stem
    for i, b in enumerate(images, start=1):
        out_name = f"{stem}_{ts}_{i:02d}.png"
        out_path = output_dir / out_name
        out_path.write_bytes(b)
        # Static mount at /outputs
        saved_urls.append(f"/outputs/{out_name}")

    # Generate QR code for gallery
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    qr_data = generate_photo_qr(job_id, base_url, str(output_dir))

    # Save gallery metadata
    _save_gallery_metadata(job_id, saved_urls[0] if saved_urls else "", ts)

    return EditResponse(
        id=job_id,
        files=saved_urls,
        qr_code_url=qr_data["qr_code_url"],
        gallery_url=qr_data["gallery_url"]
    )


class PromptCreate(BaseModel):
    name: str = Field(..., description="Short file name, e.g. 'jurassic-park'")
    category: str = Field(..., description="'background' or 'retheme'")
    text: str = Field(..., description="Prompt contents")
    pin: str | None = Field(None, description="Optional PIN; required if APP_PIN is set")


def _sanitize_name(name: str) -> str:
    safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_"))
    return safe.strip() or "prompt"


@app.post("/prompts")
def create_prompt(p: PromptCreate):
    # PIN gate (optional)
    app_pin = os.getenv("APP_PIN")
    if app_pin:
        if not p.pin or p.pin != app_pin:
            raise HTTPException(status_code=401, detail="Invalid PIN")
    category = p.category.strip().lower()
    if category not in {"background", "retheme"}:
        raise HTTPException(status_code=400, detail="category must be 'background' or 'retheme'")
    fname = _sanitize_name(p.name) + ".txt"
    target_dir = STYLES_DIR / category
    ensure_dir(target_dir)
    target = target_dir / fname
    try:
        target.write_text(p.text.strip() + "\n", encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write prompt: {e}")
    rel = str(target.relative_to(BASE_DIR)).replace("\\", "/")
    return {"ok": True, "path": rel}


# Mount static for outputs, input, and the static UI
cfg = load_config()
OUTPUT_DIR = (BASE_DIR / cfg.get("output_dir", "output")).resolve()
# Input directory for camera captures - check for DEPLOY/camera_bridge/output or bridge-dotnet output
CAMERA_OUTPUT_DIR = None
if (BASE_DIR.parent / "DEPLOY" / "camera_bridge" / "output").exists():
    CAMERA_OUTPUT_DIR = (BASE_DIR.parent / "DEPLOY" / "camera_bridge" / "output").resolve()
elif (BASE_DIR / "bridge-dotnet" / "NikonBridge" / "bin" / "Debug" / "net8.0" / "output").exists():
    CAMERA_OUTPUT_DIR = (BASE_DIR / "bridge-dotnet" / "NikonBridge" / "bin" / "Debug" / "net8.0" / "output").resolve()
else:
    CAMERA_OUTPUT_DIR = (BASE_DIR / cfg.get("input_dir", "input")).resolve()
ensure_dir(OUTPUT_DIR)
ensure_dir(CAMERA_OUTPUT_DIR)
ensure_dir(STATIC_DIR)

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.mount("/inputs", StaticFiles(directory=str(CAMERA_OUTPUT_DIR)), name="inputs")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ------------------------------
# Integrated folder watcher (optional)
# ------------------------------
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
except Exception:
    Observer = None  # Watcher disabled if watchdog missing

_watch_state = {
    "running": False,
    "watch_dir": None,
    "style_path": None,
    "editor_model": None,
    "debounce_ms": None,
    "archive_dir": None,
}
_watch_logs = deque(maxlen=500)


def _watch_log(msg: str):
    line = f"[watch] {time.strftime('%H:%M:%S')} {msg}"
    print(line)
    _watch_logs.append(line)

def _is_img(p: Path) -> bool:
    return p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def _is_stable(p: Path, debounce_ms: int) -> bool:
    try:
        m1 = p.stat().st_mtime
        size1 = p.stat().st_size
        time.sleep(max(0.2, debounce_ms / 1000.0))
        m2 = p.stat().st_mtime
        size2 = p.stat().st_size
        return m1 == m2 and size1 == size2
    except FileNotFoundError:
        return False


class _IntegratedHandler(FileSystemEventHandler):
    def __init__(self, watch_style_path: Path, editor_model: str, debounce_ms: int, output_dir: Path, archive_dir: Path | None):
        super().__init__()
        self.watch_style_path = watch_style_path
        self.editor_model = editor_model
        self.debounce_ms = debounce_ms
        self.output_dir = output_dir
        self.archive_dir = archive_dir
        self.prompt_text = self.watch_style_path.read_text(encoding="utf-8").strip() if self.watch_style_path.exists() else ""

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent) or event.is_directory:
            return
        path = Path(event.src_path)
        if not _is_img(path):
            return
        # Wait for file stability
        for _ in range(30):
            if _is_stable(path, self.debounce_ms):
                break
        else:
            _watch_log(f"skip unstable: {path}")
            return
        try:
            img_bytes = path.read_bytes()
        except Exception as e:
            _watch_log(f"read failed: {e}")
            return
        try:
            images = edit_with_gemini_image(img_bytes, self.prompt_text, model=self.editor_model)
        except Exception as e:
            _watch_log(f"edit error: {e}")
            return
        if not images:
            _watch_log("no images returned")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        stem = path.stem
        saved = []
        for i, b in enumerate(images, start=1):
            out_name = f"{stem}_{ts}_{i:02d}.png"
            out_path = self.output_dir / out_name
            out_path.write_bytes(b)
            saved.append(out_path)
        _watch_log(f"saved {len(saved)} file(s) for {path.name}")
        if self.archive_dir:
            try:
                self.archive_dir.mkdir(parents=True, exist_ok=True)
                path.replace(self.archive_dir / path.name)
                _watch_log(f"archived -> {self.archive_dir / path.name}")
            except Exception as e:
                _watch_log(f"archive failed: {e}")


_observer: Observer | None = None


def _start_integrated_watcher_from_env():
    global _observer
    if Observer is None:
        _watch_log("watchdog not installed; integrated watcher disabled")
        return
    watch_dir = os.getenv("WATCH_DIR")
    watch_style = os.getenv("WATCH_STYLE_PATH")
    # If no explicit style in env, fall back to config.json style_file
    if not watch_style:
        try:
            cfg_style = load_config().get("style_file")
            if cfg_style:
                watch_style = cfg_style
        except Exception:
            pass
    if not watch_dir:
        # Fallback to config.json input_dir if env WATCH_DIR not provided
        try:
            cfg_input = load_config().get("input_dir")
            if cfg_input:
                watch_dir = cfg_input
        except Exception:
            pass
    if not watch_dir or not watch_style:
        return  # not configured
    try:
        debounce_ms = int(os.getenv("WATCH_DEBOUNCE_MS", "1000"))
    except ValueError:
        debounce_ms = 1000
    editor_model = os.getenv("WATCH_EDITOR_MODEL", os.getenv("EDITOR_MODEL", "gemini-2.5-flash-image"))
    archive_dir_env = os.getenv("WATCH_ARCHIVE_DIR", "").strip()

    watch_path = Path(watch_dir)
    style_path = (BASE_DIR / watch_style).resolve() if not Path(watch_style).is_absolute() else Path(watch_style)
    archive_dir = Path(archive_dir_env) if archive_dir_env else None

    if not watch_path.exists():
        try:
            watch_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            _watch_log(f"cannot create WATCH_DIR: {e}")
            return
    if not style_path.exists() or not style_path.is_file():
        _watch_log(f"WATCH_STYLE_PATH must be a prompt .txt file. Got: {style_path}")
        return

    handler = _IntegratedHandler(style_path, editor_model, debounce_ms, OUTPUT_DIR, archive_dir)
    obs = Observer()
    obs.schedule(handler, str(watch_path), recursive=False)
    obs.daemon = True
    obs.start()
    _observer = obs
    _watch_state.update({
        "running": True,
        "watch_dir": str(watch_path),
        "style_path": str(style_path),
        "editor_model": editor_model,
        "debounce_ms": debounce_ms,
        "archive_dir": str(archive_dir) if archive_dir else None,
    })
    _watch_log(f"started on {watch_path} with style {style_path} -> output {OUTPUT_DIR}")


def _stop_integrated_watcher():
    global _observer
    if _observer:
        try:
            _observer.stop()
            _observer.join(timeout=5)
            _watch_log("stopped")
        finally:
            _observer = None
            _watch_state.update({"running": False})


@app.on_event("startup")
def _on_startup():
    _start_integrated_watcher_from_env()


@app.on_event("shutdown")
def _on_shutdown():
    _stop_integrated_watcher()


# ------------------------------
# Watcher control API (admin)
# ------------------------------
class WatcherStartReq(BaseModel):
    watch_dir: str
    watch_style_path: str | None = None  # Optional: if omitted, use config.json style_file
    editor_model: str | None = None
    debounce_ms: int | None = None
    archive_dir: str | None = None
    pin: str | None = None


@app.get("/watcher/status")
def watcher_status(pin: str | None = None):
    app_pin = os.getenv("APP_PIN")
    if app_pin and pin != app_pin:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    return _watch_state


@app.get("/watcher/logs")
def watcher_logs(pin: str | None = None, limit: int = 200):
    app_pin = os.getenv("APP_PIN")
    if app_pin and pin != app_pin:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    lines = list(_watch_logs)[-max(1, min(limit, 500)) :]
    return {"lines": lines}


@app.post("/watcher/start")
def watcher_start(req: WatcherStartReq):
    app_pin = os.getenv("APP_PIN")
    if app_pin and (not req.pin or req.pin != app_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    # Stop existing if running
    _stop_integrated_watcher()

    if Observer is None:
        raise HTTPException(status_code=400, detail="watchdog not installed")

    # Resolve watch dir: request field (if provided) else config.json input_dir
    watch_dir_val = (req.watch_dir or '').strip()
    if not watch_dir_val:
        cfg = load_config()
        cfg_input = cfg.get("input_dir")
        if not cfg_input:
            raise HTTPException(status_code=400, detail="No watch_dir provided. Set input_dir in config.json or provide watch_dir.")
        watch_dir_val = cfg_input
    watch_path = Path(watch_dir_val)
    # Resolve style path: request field (if provided) else config.json style_file
    if req.watch_style_path:
        style_path = Path(req.watch_style_path)
        if not style_path.is_absolute():
            style_path = (BASE_DIR / style_path).resolve()
    else:
        cfg = load_config()
        cfg_style = cfg.get("style_file")
        if not cfg_style:
            raise HTTPException(status_code=400, detail="No style specified. Set style_file in config.json or provide watch_style_path.")
        style_path = (BASE_DIR / cfg_style).resolve() if not Path(cfg_style).is_absolute() else Path(cfg_style)
    if not style_path.exists() or not style_path.is_file():
        raise HTTPException(status_code=400, detail="Resolved style must be an existing prompt .txt file")
    debounce_ms = req.debounce_ms if (isinstance(req.debounce_ms, int) and req.debounce_ms > 0) else 1000
    editor_model = req.editor_model or os.getenv("EDITOR_MODEL", "gemini-2.5-flash-image")
    archive_dir = Path(req.archive_dir) if req.archive_dir else None

    try:
        watch_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"cannot create watch_dir: {e}")

    handler = _IntegratedHandler(style_path, editor_model, debounce_ms, OUTPUT_DIR, archive_dir)
    obs = Observer()
    obs.schedule(handler, str(watch_path), recursive=False)
    obs.daemon = True
    obs.start()

    global _observer
    _observer = obs
    _watch_state.update({
        "running": True,
        "watch_dir": str(watch_path),
        "style_path": str(style_path),
        "editor_model": editor_model,
        "debounce_ms": debounce_ms,
        "archive_dir": str(archive_dir) if archive_dir else None,
    })
    _watch_log(f"started on {watch_path} with style {style_path} -> output {OUTPUT_DIR}")
    return _watch_state


class WatcherStopReq(BaseModel):
    pin: str | None = None


@app.post("/watcher/stop")
def watcher_stop(req: WatcherStopReq):
    app_pin = os.getenv("APP_PIN")
    if app_pin and (not req.pin or req.pin != app_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    _stop_integrated_watcher()
    return _watch_state


# ------------------------------
# Config read API (for UI defaults)
# ------------------------------
@app.get("/config")
def get_config():
    try:
        return load_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")


# ------------------------------
# Gallery endpoints for QR code delivery
# ------------------------------
def _save_gallery_metadata(photo_id: str, image_url: str, timestamp: str):
    """Save gallery metadata to JSON file"""
    galleries = {}
    if GALLERY_DB.exists():
        try:
            galleries = json.loads(GALLERY_DB.read_text())
        except:
            galleries = {}

    galleries[photo_id] = {
        "image_url": image_url,
        "timestamp": timestamp,
        "created": time.time()
    }

    GALLERY_DB.write_text(json.dumps(galleries, indent=2))


def _get_gallery_metadata(photo_id: str):
    """Retrieve gallery metadata"""
    if not GALLERY_DB.exists():
        return None

    try:
        galleries = json.loads(GALLERY_DB.read_text())
        return galleries.get(photo_id)
    except:
        return None


@app.get("/gallery/{photo_id}")
def gallery_page(photo_id: str):
    """Serve gallery HTML page for QR code scans"""
    gallery_html = STATIC_DIR / "gallery.html"
    if not gallery_html.exists():
        raise HTTPException(status_code=404, detail="Gallery page not found")
    return FileResponse(gallery_html)


@app.get("/api/gallery/{photo_id}")
def gallery_data(photo_id: str):
    """API endpoint to get gallery photo data"""
    metadata = _get_gallery_metadata(photo_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Gallery not found")

    return {
        "image_url": metadata["image_url"],
        "timestamp": metadata["timestamp"],
        "photo_id": photo_id
    }


class SendEmailRequest(BaseModel):
    email: str
    photo_id: str


@app.post("/send-email")
async def send_email(req: SendEmailRequest):
    """
    Send AI-enhanced photo to guest via email
    """
    # Validate email
    if not validate_email(req.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Get photo metadata
    metadata = _get_gallery_metadata(req.photo_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Build paths
    image_url = metadata["image_url"]
    # Convert URL to file path (e.g., /outputs/result_123.jpg -> output/result_123.jpg)
    if image_url.startswith("/outputs/"):
        filename = image_url.replace("/outputs/", "")
        image_path = str(BASE_DIR / "output" / filename)
    else:
        raise HTTPException(status_code=400, detail="Invalid image URL")

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    # Build gallery URL
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    gallery_url = f"{base_url}/gallery/{req.photo_id}"

    # Send email
    result = send_photo_email(req.email, req.photo_id, image_path, gallery_url)

    if result["success"]:
        return {
            "success": True,
            "message": result["message"]
        }
    else:
        raise HTTPException(status_code=500, detail=result["error"])


# ------------------------------
# SDK bridge helpers (optional integration)
# ------------------------------
def _bridge_url() -> str:
    return os.getenv("SDK_BRIDGE_URL", "http://localhost:9001").rstrip("/")


@app.get("/sdk/bridge")
def sdk_bridge_info():
    return {"bridge_url": _bridge_url()}


class ShootReq(BaseModel):
    pin: str | None = None
    bridge_url: str | None = None


@app.post("/sdk/shoot")
def sdk_shoot(req: ShootReq):
    app_pin = os.getenv("APP_PIN")
    if app_pin and (not req.pin or req.pin != app_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    # Forward to bridge
    import json as _json
    from urllib import request as _req
    from urllib.error import URLError, HTTPError
    bridge = (req.bridge_url or _bridge_url()).rstrip("/")
    url = f"{bridge}/shoot"
    body = _json.dumps({}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    try:
        r = _req.Request(url, data=body, headers=headers, method="POST")
        with _req.urlopen(r, timeout=30) as resp:
            data = resp.read().decode("utf-8")
            try:
                return _json.loads(data)
            except Exception:
                return {"ok": True, "raw": data}
    except HTTPError as e:
        try:
            err = e.read().decode("utf-8")
        except Exception:
            err = str(e)
        raise HTTPException(status_code=e.code, detail=f"Bridge error: {err}")
    except URLError as e:
        raise HTTPException(status_code=502, detail=f"Bridge unreachable at {bridge}: {e}")
