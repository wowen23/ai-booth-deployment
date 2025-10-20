# Phase 4: Web App Plan (iPad-Friendly)

## Goals
- **Host** the AI booth as a web app, accessible on iPad.
- **Keep API keys server-side**; never expose in browser.
- **Provide a simple UI** to select mode, style, upload/take photos, and view results.

## High-Level Architecture
- **Frontend (iPad browser)**
  - Single-page UI (minimal HTML/JS or React) served by backend.
  - Interacts with REST endpoints for list styles, upload/submit jobs, and fetch results.
- **Backend (Python FastAPI)**
  - Uses existing `genai_client.py` for AI calls.
  - Serves static outputs and style lists from disk.
  - Optional job queue later if needed.
- **Storage**
  - Local disk folders: `input/`, `output/`, `archive/`, and `styles/`.
  - Optional: cloud bucket when hosted in cloud.

## Backend Endpoints (FastAPI)
- `GET /health` → simple health check.
- `GET /styles?category=background|retheme` → returns list of style prompt filenames under `styles/<category>/*.txt`.
- `POST /edit`
  - Multipart form: `file` (image), `mode` (background|retheme), `style_path` (e.g., `styles/background/80s.txt`), optional `free_text`.
  - Calls `genai_client.edit_with_gemini_image()` with the uploaded image and prompt text.
  - Saves image(s) under `output/` with a generated ID and returns JSON: `{ id, files: [urls...] }`.
- `POST /generate`
  - JSON or form: `prompt` or `style_path`, `n`, `model`.
  - Calls existing generation path (optional for web MVP).
- `GET /results/{id}` (optional)
  - Returns metadata and file URLs for a previously created job.
- Static: `/outputs/*` → serves files from `output/`.

## Frontend (iPad UX)
- **Form controls**
  - Mode toggle: Background only | Retheme | (Generate optional)
  - Style dropdown populated from `/styles?category=...`
  - Free text field (optional)
  - File input: `<input type="file" accept="image/*" capture="environment">` to allow camera upload from iPad
- **Flow**
  - User selects mode + style, uploads/takes photo, clicks Submit.
  - UI calls `POST /edit` and waits for response.
  - Display returned image(s) with links to download.
  - Optional: small progress indicator.

## Security
- **Secrets**: Keep AI Studio key in server `.env` only.
- **Origins**: If exposed to public internet, set CORS to allowed origins only.
- **Rate limiting**: Basic throttling to protect API.
- **Access**: Optional PIN on the form (simple shared secret) for event environments.
- **HTTPS**: Use HTTPS for iPad (Cloudflare Tunnel or a reverse proxy with TLS).

## Hosting Options
- **Local-first (recommended for events)**
  - Run on the Windows booth PC.
  - Start server: `uvicorn server:app --host 0.0.0.0 --port 8000`.
  - Access from iPad via `http://<PC-LAN-IP>:8000`.
  - Add HTTPS with Cloudflare Tunnel for better camera permissions.
- **Cloud**
  - GCP Cloud Run (Dockerized FastAPI app).
  - Configure environment variables and mount a bucket (or save to disk and stream).

## Deployment Steps (Local)
1. Add `server.py` (FastAPI) using `genai_client.py`.
2. Add HTML page with form and JS (can be served from `templates/` or `static/`).
3. Install deps: `pip install fastapi uvicorn` (alongside existing requirements).
4. Set your `.env` with `GOOGLE_API_KEY`.
5. Run: `python -m uvicorn server:app --host 0.0.0.0 --port 8000`.
6. On iPad, open `http://<PC-IP>:8000`.

## Future Enhancements
- **PWA**: Make the site installable on iPad Home Screen.
- **Job Queue**: Add RQ/Celery if traffic spikes; return job IDs; poll `/results/{id}`.
- **Gallery**: Show a live gallery of recent outputs.
- **User delivery**: Phase “bonus” SMS/MMS integration (Twilio) to send outputs to guests.
- **Authentication**: Admin view with job logs and error tracing.

## File/Folder Reuse
- Reuse current folders: `input/`, `output/`, `archive/`, `styles/`.
- Reuse `genai_client.py` for all AI calls.

## Minimal Endpoint Contract (for quick start)
- `POST /edit`
  - Request (multipart):
    - `file`: image
    - `mode`: `background`|`retheme`
    - `style_path`: path like `styles/retheme/jurassic-park.txt`
    - `free_text` (optional)
  - Response (200):
    ```json
    {
      "id": "20251015-abc123",
      "files": ["/outputs/20251015_153000_01.png"]
    }
    ```

---

This plan keeps keys secure, works on iPad via the browser, and is a natural extension of the current Python codebase. When you’re ready, we’ll scaffold `server.py` and a minimal HTML UI and run it locally for a demo.
