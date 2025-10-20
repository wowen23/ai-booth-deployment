import os
import json
import time
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from genai_client import edit_with_gemini_image

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STYLES_DIR = BASE_DIR / "styles"
STATIC_DIR = BASE_DIR / "static"

load_dotenv()

app = FastAPI(title="AI Booth Web")

# Allow same-origin and localhost usage; adjust as needed in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.post("/edit", response_model=EditResponse)
async def edit_image(
    file: UploadFile = File(...),
    style_path: str = Form(...),
    editor_model: str = Form("gemini-2.5-flash-image"),
):
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

    return EditResponse(id=job_id, files=saved_urls)


class PromptCreate(BaseModel):
    name: str = Field(..., description="Short file name, e.g. 'jurassic-park'")
    category: str = Field(..., description="'background' or 'retheme'")
    text: str = Field(..., description="Prompt contents")


def _sanitize_name(name: str) -> str:
    safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_"))
    return safe.strip() or "prompt"


@app.post("/prompts")
def create_prompt(p: PromptCreate):
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


# Mount static for outputs and the static UI
cfg = load_config()
OUTPUT_DIR = (BASE_DIR / cfg.get("output_dir", "output")).resolve()
ensure_dir(OUTPUT_DIR)
ensure_dir(STATIC_DIR)

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
