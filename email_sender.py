"""
Email Sender for AI Photo Booth

Sends AI-enhanced photos to guests via email using SendGrid.
"""
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# SendGrid configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@aiphotobooth.com")
FROM_NAME = os.getenv("FROM_NAME", "AI Photo Booth")


def send_photo_email(to_email: str, photo_id: str, image_path: str, gallery_url: str) -> dict:
    """
    Send AI-enhanced photo via email

    Args:
        to_email: Recipient email address
        photo_id: Unique photo identifier
        image_path: Path to the photo file
        gallery_url: URL to the online gallery

    Returns:
        dict with success status and message
    """
    if not SENDGRID_API_KEY:
        return {
            "success": False,
            "error": "SendGrid API key not configured. Please set SENDGRID_API_KEY in .env file."
        }

    if not os.path.exists(image_path):
        return {
            "success": False,
            "error": f"Photo file not found: {image_path}"
        }

    try:
        # Create email message
        message = Mail(
            from_email=Email(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email),
            subject="Your AI Photo Booth Picture! 📸✨",
            html_content=Content(
                "text/html",
                f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            line-height: 1.6;
                            color: #333;
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 20px;
                        }}
                        .header {{
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            padding: 30px;
                            text-align: center;
                            border-radius: 10px 10px 0 0;
                        }}
                        .content {{
                            background: #f9f9f9;
                            padding: 30px;
                            border-radius: 0 0 10px 10px;
                        }}
                        .photo {{
                            max-width: 100%;
                            height: auto;
                            border-radius: 10px;
                            margin: 20px 0;
                        }}
                        .button {{
                            display: inline-block;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            padding: 15px 30px;
                            text-decoration: none;
                            border-radius: 8px;
                            font-weight: bold;
                            margin: 20px 0;
                        }}
                        .footer {{
                            text-align: center;
                            color: #999;
                            font-size: 0.9em;
                            margin-top: 30px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>✨ Your AI Photo is Ready! ✨</h1>
                    </div>
                    <div class="content">
                        <p>Thanks for using our AI Photo Booth!</p>
                        <p>Your AI-enhanced photo is attached to this email. You can also view and share it online:</p>

                        <center>
                            <a href="{gallery_url}" class="button">📱 View Online Gallery</a>
                        </center>

                        <p>The online gallery includes options to download in full resolution and share on social media.</p>

                        <div class="footer">
                            <p>Powered by AI Photo Booth</p>
                            <p>This is an automated message. Please do not reply to this email.</p>
                        </div>
                    </div>
                </body>
                </html>
                """
            )
        )

        # Attach the photo
        with open(image_path, 'rb') as f:
            photo_data = f.read()
            encoded_photo = base64.b64encode(photo_data).decode()

        # Determine file extension
        file_ext = Path(image_path).suffix.lower()
        if file_ext == '.jpg' or file_ext == '.jpeg':
            mime_type = 'image/jpeg'
        elif file_ext == '.png':
            mime_type = 'image/png'
        else:
            mime_type = 'application/octet-stream'

        attachment = Attachment(
            FileContent(encoded_photo),
            FileName(f'ai_photo_{photo_id}{file_ext}'),
            FileType(mime_type),
            Disposition('attachment')
        )
        message.attachment = attachment

        # Send email
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        return {
            "success": True,
            "message": f"Email sent to {to_email}",
            "status_code": response.status_code
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def validate_email(email: str) -> bool:
    """
    Basic email validation

    Args:
        email: Email address to validate

    Returns:
        True if valid format
    """
    if not email or '@' not in email:
        return False

    parts = email.split('@')
    if len(parts) != 2:
        return False

    username, domain = parts
    if not username or not domain:
        return False

    if '.' not in domain:
        return False

    return True


# Test function
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python email_sender.py <recipient_email> <photo_path>")
        print("Example: python email_sender.py user@example.com output/result_123.jpg")
        sys.exit(1)

    test_email = sys.argv[1]
    test_photo = sys.argv[2]
    test_gallery = "http://localhost:8000/gallery/test123"

    if not validate_email(test_email):
        print(f"❌ Invalid email format: {test_email}")
        sys.exit(1)

    print(f"Sending test email to {test_email}...")
    result = send_photo_email(test_email, "test123", test_photo, test_gallery)

    if result["success"]:
        print(f"✅ {result['message']}")
    else:
        print(f"❌ Error: {result['error']}")
