import os
import re
from io import BytesIO
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from PIL import Image
import google.genai as genai
from google.genai import types


def _client():
    # Load .env if present and init client with AI Studio key
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY/GOOGLE_GENAI_API_KEY for AI Studio.")
    return genai.Client(api_key=api_key)


def extract_images_from_generate_content_response(resp) -> List[bytes]:
    images: List[bytes] = []
    # The response contains candidates[0].content.parts with text and inline image data
    try:
        candidates = getattr(resp, "candidates", [])
        for cand in candidates:
            content = getattr(cand, "content", None)
            if not content:
                continue
            parts = getattr(content, "parts", [])
            for part in parts:
                # Inline image data comes as bytes in part.inline_data
                data = getattr(part, "inline_data", None)
                if data and getattr(data, "data", None):
                    images.append(data.data)
    except Exception:
        pass
    return images


def _parse_reference_images(prompt_text: str, style_dir: Optional[Path] = None) -> tuple[str, List[bytes]]:
    """
    Parse <reference:filename> tags from prompt and load the reference images.
    Returns (cleaned_prompt, list_of_image_bytes).
    """
    reference_images = []

    # Find all <reference:filename> patterns
    pattern = r'<reference:([^>]+)>'
    matches = re.findall(pattern, prompt_text)

    for filename in matches:
        if style_dir:
            ref_path = style_dir / filename
            if ref_path.exists():
                try:
                    with open(ref_path, 'rb') as f:
                        reference_images.append(f.read())
                    print(f"[GenAI] Loaded reference image: {ref_path}")
                except Exception as e:
                    print(f"[GenAI] Failed to load reference image {ref_path}: {e}")
            else:
                print(f"[GenAI] Reference image not found: {ref_path}")

    # Remove reference tags from prompt
    cleaned_prompt = re.sub(pattern, '', prompt_text).strip()

    return cleaned_prompt, reference_images


def edit_with_gemini_image(
    image_bytes: bytes,
    prompt_text: str,
    model: str = "gemini-2.5-flash-image",
    style_dir: Optional[str] = None
) -> List[bytes]:
    """
    Uses Gemini 2.5 Flash Image (AI Studio) to edit an input image according to a prompt.
    Returns a list of image bytes (PNG if output_mime_type is set accordingly).

    If style_dir is provided, parses <reference:filename> tags from prompt and includes
    those images as additional context for the AI.
    """
    client = _client()

    # Parse reference images from prompt
    style_path = Path(style_dir) if style_dir else None
    cleaned_prompt, reference_images = _parse_reference_images(prompt_text, style_path)

    # Build contents: main image + reference images + text prompt
    parts = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
    ]

    # Add reference images
    for ref_img in reference_images:
        # Detect mime type based on first bytes
        mime_type = "image/jpeg"
        if ref_img[:4] == b'\x89PNG':
            mime_type = "image/png"
        elif ref_img[:4] == b'GIF8':
            mime_type = "image/gif"
        parts.append(types.Part.from_bytes(data=ref_img, mime_type=mime_type))

    # Add the prompt text
    parts.append(types.Part.from_text(text=cleaned_prompt))

    resp = client.models.generate_content(
        model=model,
        contents=parts,
        # Note: output_mime_type is not supported in GenerateContentConfig for Gemini Image; omit it.
    )

    # Check for finish reason issues
    try:
        candidates = getattr(resp, "candidates", [])
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
            if finish_reason:
                reason_str = str(finish_reason)
                if "RECITATION" in reason_str.upper():
                    raise RuntimeError("Image generation blocked: content too similar to copyrighted material. Try a different reference image or prompt.")
                elif "SAFETY" in reason_str.upper():
                    raise RuntimeError("Image generation blocked by safety filters. Try a different prompt.")
                elif "BLOCKED" in reason_str.upper():
                    raise RuntimeError(f"Image generation blocked: {reason_str}")
    except RuntimeError:
        raise
    except Exception:
        pass  # Continue to try extracting images

    images = extract_images_from_generate_content_response(resp)
    if not images:
        # Some responses may place the image on resp.generated_images as well; attempt fallback
        gi = getattr(resp, "generated_images", None)
        if gi:
            for g in gi:
                if hasattr(g, "image") and hasattr(g.image, "image_bytes") and g.image.image_bytes:
                    images.append(g.image.image_bytes)
    return images
