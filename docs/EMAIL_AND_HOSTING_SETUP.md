# Email & Hosting Setup Guide

This guide explains how to set up email delivery and make your AI Photo Booth publicly accessible for QR codes and email delivery.

---

## Part 1: Email Setup with SendGrid

### Why SendGrid?

- **Free tier**: 100 emails/day forever (no credit card required initially)
- **Easy setup**: Simple Python SDK
- **Reliable**: Industry-standard email service
- **No spam issues**: Better deliverability than SMTP

**Cost**: Free for up to 100 emails/day (enough for small-medium events)

---

### Step 1: Create SendGrid Account

1. Go to https://signup.sendgrid.com/
2. Sign up with your email
3. Verify your email address
4. Complete account setup

---

### Step 2: Create API Key

1. Log into SendGrid dashboard
2. Go to **Settings** → **API Keys**
3. Click **Create API Key**
4. Name: "AI Photo Booth"
5. Permissions: **Full Access** (or just "Mail Send")
6. Click **Create & View**
7. **COPY THE KEY IMMEDIATELY** (you won't see it again)

---

### Step 3: Verify Sender Email

SendGrid requires you to verify the email address you'll send from:

#### Option A: Single Sender Verification (Easiest)

1. Go to **Settings** → **Sender Authentication**
2. Click **Verify a Single Sender**
3. Fill in your details:
   - **From Name**: AI Photo Booth
   - **From Email**: your-email@gmail.com (or any email you own)
4. Click **Create**
5. Check your email and click the verification link

#### Option B: Domain Authentication (More professional)

If you own a domain (e.g., yourdomain.com):

1. Go to **Settings** → **Sender Authentication**
2. Click **Authenticate Your Domain**
3. Follow DNS setup instructions
4. You can then send from any email @yourdomain.com

---

### Step 4: Configure Environment Variables

Add these to your `.env` file:

```env
# SendGrid Configuration
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FROM_EMAIL=your-email@gmail.com
FROM_NAME=AI Photo Booth

# Public URL for QR codes and emails (see Part 2)
PUBLIC_BASE_URL=http://localhost:8000
```

**Replace**:
- `SENDGRID_API_KEY` - The API key from Step 2
- `FROM_EMAIL` - The verified email from Step 3
- `FROM_NAME` - Display name guests will see

---

### Step 5: Install SendGrid Package

```bash
pip install sendgrid
```

Or if using Python 3.13:
```bash
py -3.13 -m pip install sendgrid
```

---

### Step 6: Test Email Sending

```bash
python email_sender.py your-test-email@gmail.com output/result_xxxxx.jpg
```

You should receive a test email with the photo attached!

---

## Part 2: Hosting Setup

For QR codes and emails to work, guests need to access photos online. You have 3 main options:

---

### Option 1: Local Network Only (Easiest, No Internet Required)

**Best for**: Events in a single location with WiFi

**Setup**:
1. Connect your laptop to local WiFi
2. Find your local IP address:
   ```bash
   # Windows
   ipconfig
   # Look for "IPv4 Address" (e.g., 192.168.1.100)
   ```
3. Update `.env`:
   ```env
   PUBLIC_BASE_URL=http://192.168.1.100:8000
   ```
4. Start both servers (bridge + Python)
5. Guests connect to same WiFi and scan QR codes

**Pros**:
- Free
- No internet dependency
- Fast
- Private

**Cons**:
- Guests must be on same WiFi
- Doesn't work for email (guests can't access photos later)
- IP may change if you restart router

---

### Option 2: Cloudflare Tunnel (Easiest Public Setup)

**Best for**: Quick public access without port forwarding

**Setup**:

1. **Install Cloudflare Tunnel**:
   - Download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
   - Or use: `winget install Cloudflare.cloudflared`

2. **Authenticate**:
   ```bash
   cloudflared tunnel login
   ```

3. **Create tunnel**:
   ```bash
   cloudflared tunnel create ai-booth
   ```

4. **Run tunnel** (in separate terminal):
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```

   You'll get a public URL like: `https://random-name.trycloudflare.com`

5. **Update `.env`**:
   ```env
   PUBLIC_BASE_URL=https://random-name.trycloudflare.com
   ```

6. **Restart Python server** to pick up new URL

**Pros**:
- Free
- Works anywhere in the world
- HTTPS included
- No firewall/router configuration

**Cons**:
- URL changes each time you restart tunnel
- Requires internet connection
- Slight latency

---

### Option 3: Full Cloud Deployment (Most Professional)

**Best for**: Production events, multiple locations

Several options:

#### 3A: Deploy to Cloud VM (AWS, Azure, DigitalOcean)

**AWS Lightsail** ($3.50/month):
1. Create Lightsail instance (Windows or Ubuntu)
2. Install .NET 8 and Python 3.13
3. Copy your project files
4. Configure security groups (allow ports 8000, 9001)
5. Get static IP address
6. Point domain (optional): booth.yourdomain.com
7. Update PUBLIC_BASE_URL to your IP or domain

**Pros**:
- Permanent URL
- Can use custom domain
- Reliable uptime

**Cons**:
- Monthly cost ($3.50+)
- Requires Linux knowledge
- Camera won't work (bridge requires Windows + USB)

**Note**: This works best if you separate the architecture:
- Cloud: Host Python server + photos (for QR/email)
- Local: Camera bridge on Windows laptop at event

#### 3B: Hybrid Approach (Recommended for Events)

**Camera + Bridge**: Run locally on Windows laptop at event
**Photo Storage**: Upload to cloud (S3, Cloudflare R2)
**Web UI**: Served from cloud

**Setup**:

1. **Create S3 bucket** (AWS) or **R2 bucket** (Cloudflare):
   - Make bucket public
   - Configure CORS

2. **Modify server.py** to upload photos after AI processing:
   ```python
   import boto3
   s3 = boto3.client('s3')
   s3.upload_file(local_path, 'your-bucket', filename)
   ```

3. **Update PUBLIC_BASE_URL**:
   ```env
   PUBLIC_BASE_URL=https://your-bucket.s3.amazonaws.com
   ```

**Cost**:
- S3: ~$0.023/GB/month + $0.09/GB transfer
- Cloudflare R2: FREE for first 10GB/month

**Example**: 500 photos × 2MB each = 1GB = $0.02/month on S3 or FREE on R2

---

## Recommended Setup by Use Case

### Small Event (< 50 guests, single location)
✅ **Local Network (Option 1)** + SendGrid emails
- QR codes work on local WiFi
- Emails work from anywhere

### Medium Event (50-200 guests, need remote access)
✅ **Cloudflare Tunnel (Option 2)** + SendGrid emails
- QR codes work anywhere
- Emails work from anywhere
- Free solution

### Professional/Recurring Events
✅ **Hybrid (Option 3B)** + SendGrid emails
- Camera on local laptop
- Photos on cloud storage (R2/S3)
- Web UI on cloud server
- Custom domain: booth.yourdomain.com

---

## Complete .env Configuration

```env
# Google AI
GOOGLE_API_KEY=your_google_api_key

# SendGrid Email
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FROM_EMAIL=your-verified@email.com
FROM_NAME=AI Photo Booth

# Hosting
PUBLIC_BASE_URL=https://your-public-url.com

# Camera Bridge
SDK_BRIDGE_URL=http://localhost:9001

# Optional: CORS for public access
APP_ALLOW_ORIGINS=*
```

---

## Testing Your Setup

### Test 1: Local Access
```bash
# Start both servers
# Visit: http://localhost:8000
# Capture photo → Check QR code appears
```

### Test 2: Public Access (if using tunnel/cloud)
```bash
# Visit: https://your-public-url.com
# Capture photo → Check QR code appears
# Scan QR with phone → Should open gallery
```

### Test 3: Email Delivery
```bash
# Capture photo
# Enter your email in modal
# Click "Email Me My Photo"
# Check inbox (may take 30-60 seconds)
```

---

## Troubleshooting

### "SendGrid API key not configured"
- Check `.env` file has `SENDGRID_API_KEY=SG.xxx...`
- Restart Python server after adding key

### "Sender email not verified"
- Complete Single Sender Verification in SendGrid dashboard
- Use the exact email you verified as FROM_EMAIL

### "QR code doesn't work on phone"
- Check PUBLIC_BASE_URL is accessible from phone's network
- Try opening URL directly in phone browser first
- For local network: ensure phone is on same WiFi

### "Gallery shows broken image"
- Check PUBLIC_BASE_URL matches where photos are hosted
- Verify photos exist in output/ directory
- Check file permissions

### Email not arriving
- Check spam folder
- Verify FROM_EMAIL in SendGrid dashboard
- Check SendGrid Activity Feed for delivery status
- Daily limit: 100 emails on free tier

---

## Security Best Practices

### Email Rate Limiting

Add rate limiting to prevent abuse (already included in UI):

```python
# In server.py, add rate limiting logic
from collections import defaultdict
from datetime import datetime, timedelta

email_sent = defaultdict(list)

def check_email_rate_limit(email: str, max_per_hour: int = 3) -> bool:
    """Allow max 3 emails per address per hour"""
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)

    # Clean old entries
    email_sent[email] = [t for t in email_sent[email] if t > hour_ago]

    if len(email_sent[email]) >= max_per_hour:
        return False

    email_sent[email].append(now)
    return True
```

### Environment Security

- **Never commit .env to git**
- Add `.env` to `.gitignore`
- Use strong, unique API keys
- Rotate keys periodically

### Public Access

If using public URL:
- Consider adding PIN protection (already supported via APP_PIN)
- Monitor SendGrid dashboard for unusual activity
- Set up Cloudflare WAF rules if using Cloudflare

---

## Cost Summary

### Free Setup (Recommended for small events)
- **Email**: SendGrid free tier (100/day)
- **Hosting**: Cloudflare Tunnel (free)
- **Storage**: Local disk (free)
- **Total**: $0/month

### Budget Setup (Recommended for medium events)
- **Email**: SendGrid free tier (100/day)
- **Hosting**: Cloudflare R2 (free tier)
- **Domain**: Cloudflare (free with R2)
- **Total**: $0-1/month

### Professional Setup
- **Email**: SendGrid Essentials ($19.95/month for 50k emails)
- **Hosting**: AWS Lightsail ($3.50/month)
- **Storage**: Cloudflare R2 (free tier)
- **Domain**: $12/year
- **Total**: ~$25/month

---

## Next Steps

1. ✅ Complete SendGrid setup
2. ✅ Test email locally
3. ✅ Choose hosting option
4. ✅ Configure PUBLIC_BASE_URL
5. ✅ Test end-to-end workflow
6. ✅ Run test event with friends
7. ✅ Deploy for production event!

---

**Questions?** Check the SendGrid docs at https://docs.sendgrid.com/ or create an issue.

**Last Updated**: January 6, 2026
