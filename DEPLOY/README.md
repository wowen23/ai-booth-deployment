# AI Photo Booth - Quick Start Guide

## What You Need

1. **Python 3.10 or higher** - Download from [python.org](https://www.python.org/downloads/)
2. **.NET 8.0 Runtime** - Download from [Microsoft](https://dotnet.microsoft.com/download/dotnet/8.0/runtime)
3. **Google AI Studio API Key** - Get free at [aistudio.google.com](https://aistudio.google.com/)
4. **Nikon Z6 II Camera** connected via USB

## First Time Setup (5 minutes)

### Step 1: Install Prerequisites

1. Install Python 3.10+ (if not already installed)
   - Check: Open Command Prompt and type `python --version`

2. Install .NET 8.0 Runtime (if not already installed)
   - Check: Open Command Prompt and type `dotnet --version`

### Step 2: Get Your API Key

1. Go to https://aistudio.google.com/
2. Sign in with your Google account
3. Click "Get API Key"
4. Copy your API key

### Step 3: Configure the App

1. Open the `python_server` folder
2. Create a file named `.env` (or edit if it exists)
3. Add this line (replace with your actual key):
   ```
   GOOGLE_API_KEY=your_actual_api_key_here
   WATCH_DIR=../input
   ```
4. Save and close

## Running the Photo Booth

### Easy Way (Recommended)

**Double-click `START_PHOTOBOOTH.bat`**

That's it! The script will:
- Check all dependencies
- Install Python packages (first run only)
- Start the camera bridge
- Start the web server
- Show you the URL to open

### Manual Way

If the .bat file doesn't work:

1. Open Command Prompt in this folder
2. Start camera bridge:
   ```
   camera_bridge\NikonBridge.exe
   ```
3. Open a second Command Prompt
4. Start Python server:
   ```
   cd python_server
   pip install -r requirements.txt
   python -m uvicorn server:app --host 0.0.0.0 --port 8000
   ```

## Using the Photo Booth

1. Connect your Nikon Z6 II camera via USB
2. Open your web browser to: **http://localhost:8000**
3. Click the "AI Booth" tab
4. In the "SDK Live View" section:
   - Click "Connect Camera"
   - Click "Open Stream" to see live view
   - Click "Capture Photo" to take a picture
5. Select a style and watch the AI transform your photo!

## Folder Structure

```
AI_PhotoBooth/
├── START_PHOTOBOOTH.bat    ← DOUBLE-CLICK THIS!
├── camera_bridge/           ← Camera control (runs automatically)
├── python_server/           ← Web server (runs automatically)
├── styles/                  ← AI prompt templates
├── input/                   ← Photos land here
├── output/                  ← AI-processed images
└── archive/                 ← Original photos (backed up)
```

## Troubleshooting

### Camera not detected
- Make sure camera is powered on
- Check USB cable is connected
- Close any other software using the camera (Nikon Transfer, etc.)
- Try unplugging and replugging USB

### "Python not found" error
- Install Python from python.org
- Make sure to check "Add Python to PATH" during installation

### ".NET Runtime not found" error
- Install .NET 8.0 Runtime from the Microsoft link above
- Choose "Run desktop apps" version

### Web page won't load
- Check that port 8000 is not being used by another program
- Try opening http://127.0.0.1:8000 instead
- Make sure Python server started (check Command Prompt window)

### "Invalid API Key" error
- Check your `.env` file in the `python_server` folder
- Make sure the API key is correct (no extra spaces)
- Verify the key works at aistudio.google.com

## Tips for Best Results

- **Good Lighting**: Use bright, even lighting for best AI results
- **Clean Background**: Simpler backgrounds work better for replacement
- **Camera Settings**: Use Auto mode on the camera for consistency
- **Try Different Styles**: Experiment with different prompts in the styles folder

## Stopping the App

Press `Ctrl+C` in the Command Prompt window, or just close it.
The script will automatically clean up and stop both services.

## Advanced: Creating Custom Styles

1. Go to `styles/background/` or `styles/retheme/`
2. Create a new `.txt` file with your prompt
3. Write your AI style description
4. Reload the web page to see your new style!

Example prompt for `styles/background/neon_city.txt`:
```
Replace the background with a vibrant neon-lit cyberpunk cityscape at night,
with glowing signs and flying cars. Keep the subject in sharp focus.
```

## Support

- Check `DEPLOYMENT_PLAN.md` for detailed technical information
- Review logs in the Command Prompt windows for error messages
- Ensure camera firmware is up to date

## Quick Reference

| Action | Command |
|--------|---------|
| Start Everything | Double-click `START_PHOTOBOOTH.bat` |
| Open Web UI | http://localhost:8000 |
| Stop Everything | Press Ctrl+C in terminal |
| View Processed Photos | Check `output/` folder |
| Edit Config | Edit `python_server/.env` |

---

**Ready to start?** Double-click `START_PHOTOBOOTH.bat` and have fun!
