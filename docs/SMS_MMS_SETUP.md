# SMS/MMS Photo Delivery Setup Guide

This guide walks you through setting up Telnyx to send AI-enhanced photos to guests via text message.

## Why Telnyx?

- **Low cost:** ~$0.02-0.03 per MMS (photo message)
- **No monthly fees:** Pure pay-as-you-go
- **No A2P registration:** Works immediately (unlike Twilio)
- **Simple integration:** Python SDK is easy to use

**Cost estimate:** 100 photos sent = $2-3 total

---

## Step 1: Create Telnyx Account

### Sign Up

1. Go to https://telnyx.com/sign-up
2. Create account with your email
3. Verify your email address
4. Complete account setup

### Add Payment Method

1. Go to **Billing** → **Payment Methods**
2. Add credit card (required even for trial)
3. Add initial credit (minimum $5 recommended)

**Note:** You'll only be charged for actual usage (MMS sent)

---

## Step 2: Get a Phone Number

### Purchase Number

1. Go to **Numbers** → **Buy Numbers**
2. Search for numbers in your area code
3. Look for numbers with **SMS/MMS** capability
4. Click **Buy** on a number you like (~$1/month)

**Important:** Make sure the number supports **MMS** (not just SMS)

### Configure Messaging Profile

1. Go to **Messaging** → **Messaging Profiles**
2. Click **Create Messaging Profile**
3. Name it: "Photo Booth"
4. **Webhook URL:** Leave blank for now (optional)
5. Click **Save**

### Assign Number to Profile

1. In Messaging Profiles, click your "Photo Booth" profile
2. Go to **Numbers** tab
3. Click **Add Numbers**
4. Select your purchased number
5. Click **Save**

---

## Step 3: Get API Key

### Create API Key

1. Go to **API Keys** (in left sidebar)
2. Click **Create API Key**
3. Name: "Photo Booth API"
4. Click **Create**
5. **COPY THE KEY IMMEDIATELY** (you can't see it again!)

**Save this key securely** - you'll need it in Step 4.

---

## Step 4: Configure Your Photo Booth

### Add Telnyx Credentials to `.env`

Edit your `.env` file in the project root:

```bash
# Existing variables
GOOGLE_API_KEY=your_existing_key_here

# Add these Telnyx variables
TELNYX_API_KEY=KEY...your_telnyx_api_key_here
TELNYX_PHONE_NUMBER=+12345678901
```

**Replace:**
- `TELNYX_API_KEY` - The API key you copied in Step 3
- `TELNYX_PHONE_NUMBER` - Your purchased number (format: +1XXXXXXXXXX)

### Install Telnyx Python SDK

```bash
pip install telnyx
```

### Add to requirements.txt

Edit `requirements.txt` and add:
```
telnyx>=2.0.0
```

---

## Step 5: Integration Code

### Create SMS Module

Create `sms_sender.py` in your project root:

```python
import os
import telnyx
from dotenv import load_dotenv

load_dotenv()

# Configure Telnyx
telnyx.api_key = os.getenv("TELNYX_API_KEY")
TELNYX_FROM_NUMBER = os.getenv("TELNYX_PHONE_NUMBER")


def send_photo_mms(to_phone: str, image_url: str, message: str = "Here's your AI photo!"):
    """
    Send AI-enhanced photo via MMS

    Args:
        to_phone: Recipient phone number (format: +1XXXXXXXXXX or 1XXXXXXXXXX)
        image_url: Public URL of the photo to send
        message: Text message to accompany the photo

    Returns:
        dict: Response with success status and message ID
    """
    # Normalize phone number
    if not to_phone.startswith('+'):
        if not to_phone.startswith('1'):
            to_phone = '1' + to_phone
        to_phone = '+' + to_phone

    try:
        response = telnyx.Message.create(
            from_=TELNYX_FROM_NUMBER,
            to=to_phone,
            text=message,
            media_urls=[image_url]
        )

        return {
            "success": True,
            "message_id": response.id,
            "to": to_phone,
            "cost_estimate": "$0.02-0.03"
        }

    except telnyx.error.TelnyxError as e:
        return {
            "success": False,
            "error": str(e),
            "to": to_phone
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "to": to_phone
        }


def validate_phone_number(phone: str) -> bool:
    """
    Basic phone number validation

    Args:
        phone: Phone number string

    Returns:
        bool: True if valid format
    """
    # Remove common separators
    cleaned = phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')

    # Check if it's 10 digits (US) or 11 with country code
    if len(cleaned) == 10 and cleaned.isdigit():
        return True
    if len(cleaned) == 11 and cleaned[0] == '1' and cleaned.isdigit():
        return True
    if cleaned.startswith('+1') and len(cleaned) == 12 and cleaned[1:].isdigit():
        return True

    return False


# Test function
if __name__ == "__main__":
    # Test with your own number
    test_phone = input("Enter your phone number to test (format: +1XXXXXXXXXX): ")
    test_url = "https://picsum.photos/800/600"  # Sample image

    if validate_phone_number(test_phone):
        print(f"Sending test MMS to {test_phone}...")
        result = send_photo_mms(test_phone, test_url, "Test photo from AI Booth!")
        print(f"Result: {result}")
    else:
        print("Invalid phone number format")
```

---

## Step 6: Add API Endpoint

### Update `server.py`

Add this endpoint to your FastAPI server:

```python
from sms_sender import send_photo_mms, validate_phone_number

# ... existing code ...

class SendPhotoRequest(BaseModel):
    phone_number: str
    image_filename: str  # Just the filename in output/
    message: str = "Here's your AI photo from the booth! 📸✨"

@app.post("/send-photo")
async def send_photo_sms(req: SendPhotoRequest):
    """
    Send a processed photo to a phone number via MMS
    """
    # Validate phone number
    if not validate_phone_number(req.phone_number):
        raise HTTPException(status_code=400, detail="Invalid phone number format")

    # Build public URL for the image
    # For local testing, you can use ngrok or Cloudflare Tunnel
    # For production, host images on a CDN or public server
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    image_url = f"{base_url}/outputs/{req.image_filename}"

    # Send MMS
    result = send_photo_mms(req.phone_number, image_url, req.message)

    if result["success"]:
        return {
            "success": True,
            "message": "Photo sent successfully!",
            "message_id": result["message_id"],
            "to": result["to"]
        }
    else:
        raise HTTPException(status_code=500, detail=result["error"])
```

### Add to `.env`

```env
# Public URL for MMS image delivery
# For local testing with ngrok: http://abc123.ngrok.io
# For production: https://yourdomain.com
PUBLIC_BASE_URL=http://localhost:8000
```

---

## Step 7: Update Web UI

### Add Phone Input to `static/index.html`

Add this after the style selector:

```html
<!-- Phone Number Input Section -->
<div class="row">
  <label for="phoneNumber">Phone Number (Optional)</label>
  <input
    id="phoneNumber"
    type="tel"
    placeholder="+1 (555) 123-4567"
    pattern="[\+]?[0-9]{10,12}"
  />
  <button id="sendToPhone" disabled>📱 Text Me My Photo</button>
</div>

<div id="smsStatus" class="muted"></div>
```

### Add JavaScript Handler

Add to the `<script>` section:

```javascript
// Send photo via SMS
document.getElementById('sendToPhone').addEventListener('click', async () => {
  const phoneInput = document.getElementById('phoneNumber');
  const phone = phoneInput.value.trim();
  const statusDiv = document.getElementById('smsStatus');

  if (!phone) {
    statusDiv.textContent = 'Please enter a phone number';
    return;
  }

  // Get the latest result image filename
  const resultImgs = document.querySelectorAll('#results img');
  if (resultImgs.length === 0) {
    statusDiv.textContent = 'No photo to send yet!';
    return;
  }

  const latestImg = resultImgs[0];
  const filename = latestImg.src.split('/').pop();

  statusDiv.textContent = 'Sending...';

  try {
    const response = await fetch('/send-photo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone_number: phone,
        image_filename: filename
      })
    });

    const result = await response.json();

    if (result.success) {
      statusDiv.textContent = '✅ Photo sent to ' + result.to;
      statusDiv.style.color = 'green';
    } else {
      statusDiv.textContent = '❌ Failed to send: ' + result.error;
      statusDiv.style.color = 'red';
    }
  } catch (error) {
    statusDiv.textContent = '❌ Error: ' + error.message;
    statusDiv.style.color = 'red';
  }
});

// Enable/disable send button based on phone input
document.getElementById('phoneNumber').addEventListener('input', (e) => {
  const sendBtn = document.getElementById('sendToPhone');
  sendBtn.disabled = !e.target.value.trim();
});
```

---

## Step 8: Testing

### Local Testing (with ngrok)

Since MMS requires public image URLs, use ngrok for local testing:

1. **Install ngrok:** https://ngrok.com/download

2. **Start ngrok:**
   ```bash
   ngrok http 8000
   ```

3. **Copy the public URL** (e.g., `https://abc123.ngrok.io`)

4. **Update `.env`:**
   ```env
   PUBLIC_BASE_URL=https://abc123.ngrok.io
   ```

5. **Restart your servers**

6. **Test the integration:**
   ```bash
   # Test SMS sender directly
   python sms_sender.py
   ```

### Production Testing

Once deployed with a public domain:

```env
PUBLIC_BASE_URL=https://yourdomain.com
```

---

## Step 9: Workflow Integration

### Automatic SMS After AI Processing

To automatically offer SMS delivery after processing:

```python
# In server.py, after AI processing completes

@app.post("/edit", response_model=EditResponse)
async def edit_image(...):
    # ... existing AI processing code ...

    # After saving output image
    result_files = [...]  # Your result files

    return {
        "id": unique_id,
        "files": result_files,
        "sms_available": True  # Signal to UI that SMS is ready
    }
```

---

## Troubleshooting

### "Invalid API Key"
- Check that `TELNYX_API_KEY` in `.env` is correct
- Make sure key starts with `KEY...`
- Verify key hasn't been deleted in Telnyx dashboard

### "From number not verified"
- Ensure phone number is assigned to a Messaging Profile
- Check number format is correct (+1XXXXXXXXXX)
- Verify number has MMS capability

### "Image not loading in MMS"
- Image URL must be publicly accessible
- Use ngrok for local testing
- Check image size (recommended < 500KB)
- Ensure image is JPEG or PNG format

### "Message delivery failed"
- Recipient number must be valid US/Canada number
- Check Telnyx balance (needs credit)
- Review Telnyx dashboard for delivery logs

---

## Cost Management

### Monitor Usage

1. **Telnyx Dashboard** → **Billing** → **Usage**
2. Set up **Balance Alerts**:
   - Go to **Billing** → **Alerts**
   - Set threshold (e.g., $5 remaining)
   - Get email when balance is low

### Budget Example

| Event Size | Messages | Estimated Cost |
|------------|----------|----------------|
| Small (25 guests) | 25 | $0.50-0.75 |
| Medium (50 guests) | 50 | $1.00-1.50 |
| Large (100 guests) | 100 | $2.00-3.00 |
| Very Large (200 guests) | 200 | $4.00-6.00 |

**Add $5-10 to account before each event to ensure smooth operation.**

---

## Security Best Practices

### Rate Limiting

Add rate limiting to prevent abuse:

```python
from collections import defaultdict
from datetime import datetime, timedelta

# Simple rate limiter (in production, use Redis)
sms_sent = defaultdict(list)

def check_rate_limit(phone: str, max_per_hour: int = 3) -> bool:
    """Allow max 3 SMS per phone number per hour"""
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)

    # Clean old entries
    sms_sent[phone] = [t for t in sms_sent[phone] if t > hour_ago]

    if len(sms_sent[phone]) >= max_per_hour:
        return False

    sms_sent[phone].append(now)
    return True
```

### Input Validation

Always validate phone numbers before sending:

```python
import re

def sanitize_phone(phone: str) -> str:
    """Remove common separators and validate"""
    # Remove everything except digits and +
    cleaned = re.sub(r'[^\d\+]', '', phone)

    # Ensure US/Canada format
    if not cleaned.startswith('+'):
        cleaned = '+1' + cleaned.lstrip('1')

    return cleaned
```

---

## Alternative: Free QR Code Delivery

If you want to avoid SMS costs entirely:

```python
import qrcode

def generate_photo_qr(photo_filename: str) -> str:
    """Generate QR code linking to photo"""
    url = f"{PUBLIC_BASE_URL}/outputs/{photo_filename}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    qr_path = f"output/qr_{photo_filename}.png"
    img.save(qr_path)

    return qr_path
```

Display QR code on screen for guests to scan with their phone camera.

---

## Next Steps

1. ✅ Sign up for Telnyx
2. ✅ Buy phone number
3. ✅ Get API key
4. ✅ Add credentials to `.env`
5. ✅ Install `telnyx` package
6. ✅ Create `sms_sender.py`
7. ✅ Test with your own phone
8. ✅ Add UI elements
9. ✅ Test end-to-end
10. ✅ Deploy for events!

---

**Questions or issues?** Check the troubleshooting section or Telnyx support at https://telnyx.com/support

**Last Updated:** January 6, 2026
