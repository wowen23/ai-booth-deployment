import os
import argparse
from datetime import datetime
from pathlib import Path
from io import BytesIO

from dotenv import load_dotenv
from PIL import Image
from google import genai
from google.genai import types


def parse_args():
    parser = argparse.ArgumentParser(description="Generate images with Google Imagen via google-genai")
    parser.add_argument("prompt", type=str, nargs="?", help="Text prompt for image generation")
    parser.add_argument("--n", type=int, default=1, help="Number of images to generate (1-8)")
    parser.add_argument(
        "--model",
        type=str,
        default="imagen-3.0-generate-002",
        help="Model name, e.g., imagen-3.0-generate-002 (Vertex) or gemini-2.5-flash-image (Developer API)",
    )
    parser.add_argument("--output", type=str, default="output", help="Output directory for generated images")
    parser.add_argument("--list-models", action="store_true", help="List available base models for this API key and exit")
    parser.add_argument("--prompt-file", type=str, help="Path to a text file whose contents will be used as the prompt")
    return parser.parse_args()


def main():
    # Load environment variables from .env if present
    load_dotenv()

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing API key. Set GOOGLE_API_KEY (or GOOGLE_GENAI_API_KEY) in your environment or .env file."
        )

    args = parse_args()

    # Validate n
    n = max(1, min(8, args.n))

    # Prepare client
    client = genai.Client(api_key=api_key)

    # If requested, list available models and exit
    if args.list_models:
        print("Listing available models for this API key:\n")
        try:
            for m in client.models.list():
                try:
                    name = getattr(m, "name", None) or getattr(m, "model", None) or str(m)
                    desc = getattr(m, "description", "")
                    print(f"- {name}" + (f" — {desc}" if desc else ""))
                except Exception:
                    print(f"- {m}")
        except Exception as e:
            print(f"Failed to list models: {e}")
        return

    # Resolve prompt text: support positional string, @file syntax, or --prompt-file
    prompt_text = None
    if args.prompt:
        if args.prompt.startswith("@"):
            file_path = args.prompt[1:]
            try:
                prompt_text = Path(file_path).read_text(encoding="utf-8").strip()
            except Exception as e:
                raise SystemExit(f"Failed to read prompt file '{file_path}': {e}")
        else:
            prompt_text = args.prompt
    elif args.prompt_file:
        try:
            prompt_text = Path(args.prompt_file).read_text(encoding="utf-8").strip()
        except Exception as e:
            raise SystemExit(f"Failed to read prompt file '{args.prompt_file}': {e}")

    # If prompt is missing and not listing models, fail fast
    if not args.list_models and not prompt_text:
        raise SystemExit("Prompt is required unless --list-models is specified. Use a positional prompt, '@path/to/file.txt', or --prompt-file.")

    # Ensure output directory exists
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Normalize model name to accept either 'models/<id>' or '<id>'
    model_name = args.model.split("/", 1)[1] if args.model.startswith("models/") else args.model

    print(f"Generating {n} image(s) with model {model_name}...")

    try:
        resp = client.models.generate_images(
            model=model_name,
            prompt=prompt_text,
            config=types.GenerateImagesConfig(
                number_of_images=n,
                include_rai_reason=True,
                output_mime_type="image/png",
                # You can add guidance/negative_prompt/safety_settings here as needed
            ),
        )
    except Exception as e:
        # Provide helpful guidance for common NOT_FOUND when using Imagen without Vertex setup
        msg = str(e)
        hint = ""
        if "NOT_FOUND" in msg or "models/" in msg:
            if model_name.startswith("imagen-") and os.getenv("GOOGLE_GENAI_USE_VERTEXAI") not in ("True", "true", "1"):
                hint = (
                    "\nHint: Imagen models are served via Vertex AI. Set environment variables and auth first, e.g.\n"
                    "  $env:GOOGLE_GENAI_USE_VERTEXAI='True'\n"
                    "  $env:GOOGLE_CLOUD_PROJECT='<your-project-id>'\n"
                    "  $env:GOOGLE_CLOUD_LOCATION='us-central1'\n"
                    "Then authenticate with gcloud CLI (Application Default Credentials) or a service account."
                )
        raise SystemExit(f"Image generation failed: {e}{hint}")

    if not getattr(resp, "generated_images", None):
        raise SystemExit("No images returned by API.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = []

    for idx, gen_img in enumerate(resp.generated_images, start=1):
        # The SDK returns an object with .image that can be displayed. Convert to bytes if necessary.
        try:
            img_bytes = None
            if hasattr(gen_img, "image") and hasattr(gen_img.image, "image_bytes") and gen_img.image.image_bytes:
                img_bytes = gen_img.image.image_bytes
            elif hasattr(gen_img, "image") and isinstance(gen_img.image, (bytes, bytearray)):
                img_bytes = gen_img.image

            if img_bytes is None:
                # Fallback: try to use PIL show/save if object supports .show(); otherwise, error.
                # We prefer saving to disk using bytes for reliability.
                raise ValueError("Could not extract image bytes from response.")

            img = Image.open(BytesIO(img_bytes))
            fname = out_dir / f"{timestamp}_{idx:02d}.png"
            img.save(fname)
            saved.append(fname)
        except Exception as e:
            print(f"Warning: failed to process image {idx}: {e}")

    if not saved:
        raise SystemExit("Failed to save any images.")

    print("Saved images:")
    for p in saved:
        print(f" - {p}")


if __name__ == "__main__":
    main()
