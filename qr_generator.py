"""
QR Code Generator for AI Photo Booth

Generates QR codes that link to guest photo galleries.
"""
import os
import qrcode
from pathlib import Path
from io import BytesIO
import base64


def generate_qr_code(url: str, output_path: str = None, size: int = 10) -> str:
    """
    Generate a QR code for the given URL

    Args:
        url: The URL to encode in the QR code
        output_path: Optional path to save QR code image (if None, returns base64)
        size: Box size for QR code (default 10 = medium size)

    Returns:
        If output_path provided: path to saved QR code
        If output_path is None: base64 encoded image string
    """
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,  # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=size,
        border=4,
    )

    # Add data
    qr.add_data(url)
    qr.make(fit=True)

    # Create image
    img = qr.make_image(fill_color="black", back_color="white")

    # Save or return base64
    if output_path:
        img.save(output_path)
        return output_path
    else:
        # Return as base64 for embedding in HTML
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"


def generate_photo_qr(photo_id: str, base_url: str, output_dir: str = "output") -> dict:
    """
    Generate QR code for a specific photo gallery

    Args:
        photo_id: Unique identifier for the photo session
        base_url: Base URL of the application (e.g., http://localhost:8000)
        output_dir: Directory to save QR code image

    Returns:
        dict with qr_code_path and gallery_url
    """
    # Build gallery URL
    gallery_url = f"{base_url}/gallery/{photo_id}"

    # Generate QR code filename
    qr_filename = f"qr_{photo_id}.png"
    qr_path = Path(output_dir) / qr_filename

    # Ensure output directory exists
    qr_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate and save QR code
    generate_qr_code(gallery_url, str(qr_path), size=10)

    return {
        "qr_code_path": str(qr_path),
        "qr_code_url": f"/outputs/{qr_filename}",
        "gallery_url": gallery_url
    }


def get_qr_code_base64(url: str) -> str:
    """
    Generate QR code as base64 string (for direct embedding in HTML)

    Args:
        url: URL to encode

    Returns:
        Base64 encoded QR code image (data URI)
    """
    return generate_qr_code(url, output_path=None, size=10)


# Test function
if __name__ == "__main__":
    # Test QR code generation
    test_url = "http://localhost:8000/gallery/test123"

    print("Generating QR code...")
    result = generate_photo_qr("test123", "http://localhost:8000")

    print(f"✅ QR code saved to: {result['qr_code_path']}")
    print(f"📱 Gallery URL: {result['gallery_url']}")
    print(f"🔗 QR code URL: {result['qr_code_url']}")

    # Also test base64 generation
    base64_qr = get_qr_code_base64(test_url)
    print(f"📊 Base64 length: {len(base64_qr)} characters")
