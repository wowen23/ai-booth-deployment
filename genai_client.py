import os
from io import BytesIO
from typing import List

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


def edit_with_gemini_image(image_bytes: bytes, prompt_text: str, model: str = "gemini-2.5-flash-image") -> List[bytes]:
    """
    Uses Gemini 2.5 Flash Image (AI Studio) to edit an input image according to a prompt.
    Returns a list of image bytes (PNG if output_mime_type is set accordingly).
    """
    client = _client()

    # Build contents: image + text prompt
    parts = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),  # best-effort; model handles
        types.Part.from_text(text=prompt_text),
    ]

    resp = client.models.generate_content(
        model=model,
        contents=parts,
        # Note: output_mime_type is not supported in GenerateContentConfig for Gemini Image; omit it.
    )

    images = extract_images_from_generate_content_response(resp)
    if not images:
        # Some responses may place the image on resp.generated_images as well; attempt fallback
        gi = getattr(resp, "generated_images", None)
        if gi:
            for g in gi:
                if hasattr(g, "image") and hasattr(g.image, "image_bytes") and g.image.image_bytes:
                    images.append(g.image.image_bytes)
    return images
