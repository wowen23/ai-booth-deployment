using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Configuration;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Formats.Jpeg;
using SixLabors.ImageSharp.PixelFormats;
using DotNetEnv;
using NikonMaidWrapper;

var builder = WebApplication.CreateBuilder(args);

// Configuration (env + appsettings)
// Load .env so WATCH_DIR/BRIDGE_* can be set there
Env.Load();
var config = builder.Configuration;
var loggerFactory = LoggerFactory.Create(b => b.AddConsole());
var logger = loggerFactory.CreateLogger("NikonBridge");

// Add CORS support for web UI
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

var app = builder.Build();

// Enable CORS
app.UseCors();

// Read settings
var watchDir = Environment.GetEnvironmentVariable("WATCH_DIR")
              ?? config["WATCH_DIR"]
              ?? System.IO.Path.Combine(AppContext.BaseDirectory, "output");
var port = Environment.GetEnvironmentVariable("BRIDGE_PORT") ?? "9001";
var fps = int.TryParse(Environment.GetEnvironmentVariable("BRIDGE_FPS"), out var tmpFps) ? tmpFps : 15;

// SDK placeholder state + MAID wrapper instance
var sdk = new SdkStub(logger, watchDir, fps);
sdk.CheckNikonDlls();

// Try to create MAID wrapper - may fail if DLLs aren't found
MaidBridge? maid = null;
try
{
    maid = new MaidBridge();
    logger.LogInformation("MAID wrapper initialized successfully");
}
catch (Exception ex)
{
    logger.LogWarning("Failed to initialize MAID wrapper: {Error}. SDK features will not be available.", ex.Message);
}

app.MapGet("/status", () => Results.Json(new {
    ok = true,
    connected = sdk.Connected,
    live = sdk.LiveRunning,
    watch_dir = sdk.WatchDir,
    fps = sdk.Fps,
    nikon_dlls = sdk.DllStatus
}));

app.MapGet("/live.mjpg", async context => {
    if (!sdk.LiveRunning)
    {
        context.Response.StatusCode = StatusCodes.Status409Conflict;
        await context.Response.WriteAsJsonAsync(new {
            detail = "Live view not running. Call /sdk/start-live first."
        });
        return;
    }
    if (maid == null)
    {
        context.Response.StatusCode = StatusCodes.Status500InternalServerError;
        await context.Response.WriteAsJsonAsync(new { detail = "MAID wrapper not initialized" });
        return;
    }

    // MJPEG stream - multipart/x-mixed-replace with boundary
    context.Response.ContentType = "multipart/x-mixed-replace; boundary=frame";
    context.Response.Headers.Append("Cache-Control", "no-cache, no-store, must-revalidate");
    context.Response.Headers.Append("Pragma", "no-cache");
    context.Response.Headers.Append("Expires", "0");

    try
    {
        while (!context.RequestAborted.IsCancellationRequested && sdk.LiveRunning)
        {
            var frameBytes = maid.GetLiveFrame();
            if (frameBytes != null && frameBytes.Length > 0)
            {
                await context.Response.WriteAsync("--frame\r\n");
                await context.Response.WriteAsync($"Content-Type: image/jpeg\r\n");
                await context.Response.WriteAsync($"Content-Length: {frameBytes.Length}\r\n\r\n");
                await context.Response.Body.WriteAsync(frameBytes, 0, frameBytes.Length);
                await context.Response.WriteAsync("\r\n");
                await context.Response.Body.FlushAsync();
            }

            // Limit to 1 FPS for testing
            await Task.Delay(1000, context.RequestAborted);
        }
    }
    catch (Exception ex) when (ex is OperationCanceledException || context.RequestAborted.IsCancellationRequested)
    {
        // Client disconnected - normal
    }
    catch (Exception ex)
    {
        logger.LogError(ex, "Error streaming live view");
    }
});

app.MapPost("/shoot", async context => {
    try
    {
        logger.LogInformation("Shoot endpoint called");

        if (!sdk.Connected)
        {
            logger.LogWarning("Shoot: Not connected");
            context.Response.StatusCode = StatusCodes.Status409Conflict;
            await context.Response.WriteAsJsonAsync(new { detail = "Not connected. Call /sdk/connect first." });
            return;
        }

        if (maid == null)
        {
            logger.LogWarning("Shoot: MAID wrapper not initialized");
            context.Response.StatusCode = StatusCodes.Status500InternalServerError;
            await context.Response.WriteAsJsonAsync(new { detail = "MAID wrapper not initialized" });
            return;
        }

        // Trigger the shutter
        logger.LogInformation("Triggering camera shutter...");
        maid.Shoot(watchDir); // This triggers the shutter, image saves to SD card

        // Disconnect SDK to allow MTP access
        logger.LogInformation("Disconnecting SDK to enable MTP access...");
        try
        {
            maid.StopLive();
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Error stopping live view (may already be stopped)");
        }

        try
        {
            maid.Disconnect();
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Error disconnecting SDK");
        }

        // Wait for camera to release USB and enable MTP
        logger.LogInformation("Waiting for camera to enable MTP access...");
        await Task.Delay(3000);

        // Try to copy via MTP
        logger.LogInformation("Attempting to copy from MTP...");
        var copiedFile = CopyMostRecentPhotoFromMTP("Z 6_2", watchDir, logger);

        if (copiedFile != null)
        {
            logger.LogInformation("Successfully copied: {File}", copiedFile);
            await context.Response.WriteAsJsonAsync(new { ok = true, files = new[] { copiedFile }, message = "Photo captured and copied. Note: Camera was disconnected - click 'Connect Camera' to resume live view." });
        }
        else
        {
            logger.LogWarning("Photo captured but file copy from MTP failed");
            await context.Response.WriteAsJsonAsync(new { ok = true, files = new string[0], message = "Photo captured to camera SD card, but MTP transfer failed. Click 'Connect Camera' to reconnect." });
        }
    }
    catch (Exception ex)
    {
        logger.LogError(ex, "Error in shoot endpoint");
        context.Response.StatusCode = StatusCodes.Status500InternalServerError;
        await context.Response.WriteAsJsonAsync(new { detail = ex.ToString() });
    }
});

// Retry MTP copy without triggering shutter
app.MapPost("/retry-copy", async (HttpContext context) =>
{
    try
    {
        logger.LogInformation("Retrying MTP copy...");

        // Try to copy via MTP multiple times
        string? copiedFile = null;
        for (int attempt = 1; attempt <= 5; attempt++)
        {
            logger.LogInformation("MTP copy attempt {Attempt}/5...", attempt);
            copiedFile = CopyMostRecentPhotoFromMTP("Z 6_2", watchDir, logger);

            if (copiedFile != null)
            {
                logger.LogInformation("Successfully copied on attempt {Attempt}: {File}", attempt, copiedFile);
                break;
            }

            if (attempt < 5)
            {
                logger.LogWarning("MTP copy attempt {Attempt} failed, waiting 3 seconds before retry...", attempt);
                await Task.Delay(3000);
            }
        }

        if (copiedFile != null)
        {
            await context.Response.WriteAsJsonAsync(new { ok = true, files = new[] { copiedFile }, message = $"Successfully copied: {Path.GetFileName(copiedFile)}" });
        }
        else
        {
            logger.LogWarning("All MTP copy attempts failed");
            await context.Response.WriteAsJsonAsync(new { ok = false, files = new string[0], message = "Failed to copy from MTP after 5 attempts. Check that camera is not connected to SDK." });
        }
    }
    catch (Exception ex)
    {
        logger.LogError(ex, "Error in retry-copy endpoint");
        context.Response.StatusCode = StatusCodes.Status500InternalServerError;
        await context.Response.WriteAsJsonAsync(new { detail = ex.ToString() });
    }
});

// SDK control scaffolding
app.MapPost("/sdk/connect", () => {
    try
    {
        if (maid == null)
        {
            return Results.Problem("MAID wrapper not initialized. Check that all Nikon SDK DLLs are present.", statusCode: 500);
        }
        var ok = maid.Connect();
        if (ok) sdk.Connect();
        return Results.Json(new { ok = ok, connected = ok });
    }
    catch (Exception ex)
    {
        return Results.Problem(ex.Message, statusCode: 500);
    }
});

app.MapPost("/sdk/disconnect", () => {
    try
    {
        if (maid != null) maid.Disconnect();
        sdk.Disconnect();
        return Results.Json(new { ok = true, connected = false });
    }
    catch (Exception ex)
    {
        return Results.Problem(ex.Message, statusCode: 500);
    }
});

app.MapPost("/sdk/start-live", () => {
    if (!sdk.Connected) return Results.Conflict(new { detail = "Not connected. Call /sdk/connect first." });
    if (!sdk.CanUseSdk) return Results.StatusCode(StatusCodes.Status503ServiceUnavailable);
    try
    {
        if (maid == null) return Results.Problem("MAID wrapper not initialized", statusCode: 500);
        var ok = maid.StartLive();
        if (ok) sdk.StartLive();
        return Results.Json(new { ok = ok, live = sdk.LiveRunning });
    }
    catch (Exception ex)
    {
        return Results.Problem(ex.Message, statusCode: 500);
    }
});

app.MapPost("/sdk/stop-live", () => {
    try
    {
        if (maid != null) maid.StopLive();
        sdk.StopLive();
        return Results.Json(new { ok = true, live = sdk.LiveRunning });
    }
    catch (Exception ex)
    {
        return Results.Problem(ex.Message, statusCode: 500);
    }
});

app.MapGet("/sdk/test-mode", () => {
    if (!sdk.Connected) return Results.Conflict(new { detail = "Not connected. Call /sdk/connect first." });
    try
    {
        if (maid == null) return Results.Problem("MAID wrapper not initialized", statusCode: 500);
        var result = maid.TestLiveViewMode();
        return Results.Text(result, "text/plain");
    }
    catch (Exception ex)
    {
        return Results.Problem(ex.Message, statusCode: 500);
    }
});

app.MapGet("/sdk/test-frame", () => {
    if (!sdk.LiveRunning) return Results.Conflict(new { detail = "Live view not running" });
    try
    {
        if (maid == null) return Results.Problem("MAID wrapper not initialized", statusCode: 500);

        logger.LogInformation("Getting test frame...");
        var frameBytes = maid.GetLiveFrame();
        logger.LogInformation($"Got {frameBytes?.Length ?? 0} bytes");

        if (frameBytes == null || frameBytes.Length == 0)
        {
            return Results.Problem("No frame data received", statusCode: 500);
        }

        // Save to multiple locations for testing
        var testPath1 = Path.Combine(watchDir, "test_frame.jpg");
        var testPath2 = Path.Combine(AppContext.BaseDirectory, "test_frame.jpg");
        var testPath3 = @"C:\Users\willi\image_gen\test_images\test_frame.jpg";

        File.WriteAllBytes(testPath1, frameBytes);
        File.WriteAllBytes(testPath2, frameBytes);
        File.WriteAllBytes(testPath3, frameBytes);

        logger.LogInformation($"Saved to: {testPath1}");
        logger.LogInformation($"Saved to: {testPath2}");
        logger.LogInformation($"Saved to: {testPath3}");

        // Also return as JPEG
        return Results.File(frameBytes, "image/jpeg");
    }
    catch (Exception ex)
    {
        logger.LogError(ex, "Error getting test frame");
        return Results.Problem(ex.Message, statusCode: 500);
    }
});

app.Lifetime.ApplicationStarted.Register(() => {
    logger.LogInformation("NikonBridge starting on port {Port}, watch_dir={WatchDir}", port, watchDir);
});

await app.RunAsync($"http://0.0.0.0:{port}");

return;

// MTP file copy helper
static string? CopyMostRecentPhotoFromMTP(string deviceName, string destDir, ILogger logger)
{
    try
    {
        logger.LogInformation("Accessing MTP device: {Device}", deviceName);

        // Create Shell object to access MTP devices
        Type shellType = Type.GetTypeFromProgID("Shell.Application");
        if (shellType == null)
        {
            logger.LogError("Failed to get Shell.Application COM object");
            return null;
        }

        dynamic shell = Activator.CreateInstance(shellType);

        // Get "This PC" namespace (0x11 = ssfDRIVES)
        dynamic folder = shell.NameSpace(0x11);

        // Find the camera device
        dynamic? cameraFolder = null;
        foreach (dynamic item in folder.Items())
        {
            if (item.Name == deviceName)
            {
                string deviceNameStr = item.Name;
                logger.LogInformation("Found device: {Name}", deviceNameStr);
                cameraFolder = item.GetFolder;
                break;
            }
        }

        if (cameraFolder == null)
        {
            logger.LogWarning("Camera device '{Device}' not found", deviceName);
            return null;
        }

        // Navigate to storage (could be "Removable storage" or "SD card" or similar)
        dynamic? storageFolder = null;
        logger.LogInformation("Enumerating camera storage items...");
        foreach (dynamic item in cameraFolder.Items())
        {
            string itemName = item.Name;
            bool isFolder = item.IsFolder;
            logger.LogInformation("  Item: {Name} (IsFolder: {IsFolder})", itemName, isFolder);

            if (isFolder && (itemName.Contains("Removable") || itemName.Contains("SD") || itemName.Contains("Storage") || itemName.Contains("Card")))
            {
                logger.LogInformation("Found storage: {Name}", itemName);
                storageFolder = item.GetFolder;
                break;
            }
        }

        if (storageFolder == null)
        {
            logger.LogWarning("Storage not found - tried looking for folders with 'Removable', 'SD', 'Storage', or 'Card' in the name");
            return null;
        }

        // Navigate to DCIM
        dynamic? dcimFolder = null;
        foreach (dynamic item in storageFolder.Items())
        {
            if (item.Name == "DCIM")
            {
                logger.LogInformation("Found DCIM folder");
                dcimFolder = item.GetFolder;
                break;
            }
        }

        if (dcimFolder == null)
        {
            logger.LogWarning("DCIM folder not found");
            return null;
        }

        // Find most recent folder in DCIM by name (e.g., 101NZ6_2, 102NZ6_2, 103NZ6_2)
        // Folders are numbered sequentially, so highest number = most recent
        // Then find the most recent file in that folder
        string? highestFolderName = null;
        dynamic? newestFolder = null;

        // First pass: Find the folder with the highest name (alphabetically last)
        foreach (dynamic photoFolder in dcimFolder.Items())
        {
            if (photoFolder.IsFolder)
            {
                string folderName = photoFolder.Name;
                if (highestFolderName == null || string.Compare(folderName, highestFolderName, StringComparison.Ordinal) > 0)
                {
                    highestFolderName = folderName;
                    newestFolder = photoFolder;
                }
            }
        }

        if (newestFolder == null)
        {
            logger.LogWarning("No photo folders found in DCIM");
            return null;
        }

        string mostRecentFolderName = newestFolder.Name;
        logger.LogInformation("Most recent folder: {Name}", mostRecentFolderName);

        // Second pass: Find the most recent file in the most recent folder
        var targetFolder = newestFolder.GetFolder;
        DateTime? newestTime = null;
        dynamic? newestFile = null;

        foreach (dynamic file in targetFolder.Items())
        {
            if (!file.IsFolder)
            {
                try
                {
                    var modTime = file.ModifyDate;
                    if (newestTime == null || modTime > newestTime)
                    {
                        newestTime = modTime;
                        newestFile = file;
                    }
                }
                catch
                {
                    // Skip items without ModifyDate
                }
            }
        }

        if (newestFile == null)
        {
            logger.LogWarning("No photos found in DCIM");
            return null;
        }

        // Copy the file
        string baseName = newestFile.Name.ToString();
        logger.LogInformation("Copying {Source} to {DestDir}", baseName, destDir);

        // Use Shell to copy the file
        var destFolderObj = shell.NameSpace(destDir);
        destFolderObj.CopyHere(newestFile, 16); // 16 = respond "Yes to All"

        // Wait a moment for copy to complete
        System.Threading.Thread.Sleep(2000);

        // CopyHere() automatically adds proper extension (.JPG, .NEF, etc.)
        // Try common extensions to find the copied file
        var possiblePaths = new[]
        {
            Path.Combine(destDir, baseName),
            Path.Combine(destDir, $"{baseName}.JPG"),
            Path.Combine(destDir, $"{baseName}.jpg"),
            Path.Combine(destDir, $"{baseName}.NEF"),
            Path.Combine(destDir, $"{baseName}.nef"),
            Path.Combine(destDir, $"{baseName}.JPEG"),
            Path.Combine(destDir, $"{baseName}.jpeg")
        };

        foreach (var path in possiblePaths)
        {
            if (File.Exists(path))
            {
                string copiedPath = path;
                logger.LogInformation("Successfully copied file: {Path}", copiedPath);
                return path;
            }
        }

        logger.LogWarning("File copy may have failed - file not found at any expected path");
        return null;
    }
    catch (Exception ex)
    {
        logger.LogError(ex, "Error copying from MTP device");
        return null;
    }
}

// --- Stubs to be replaced with Nikon SDK integration ---
class SdkStub
{
    private readonly ILogger _logger;
    public string WatchDir { get; }
    public int Fps { get; }
    public bool Connected { get; private set; } = false;
    public bool LiveRunning { get; private set; } = false;
    public bool CanUseSdk { get; private set; } = false;
    public object DllStatus { get; private set; } = new { };

    public SdkStub(ILogger logger, string watchDir, int fps)
    {
        _logger = logger;
        WatchDir = watchDir;
        Directory.CreateDirectory(WatchDir);
        Fps = fps;
        // Later: initialize Nikon SDK, connect, set Connected=true
    }

    public void CheckNikonDlls()
    {
        var baseDir = AppContext.BaseDirectory;
        var files = new[] { "Type0029.md3", "NkdPTP.dll", "dnssd.dll", "NkRoyalmile.dll" };
        var found = files.Select(f => new { file = f, exists = File.Exists(Path.Combine(baseDir, f)) }).ToArray();
        DllStatus = new { baseDir, files = found };
        CanUseSdk = found.All(x => x.exists);
        if (!CanUseSdk)
        {
            _logger.LogWarning("Nikon SDK DLLs not all present in {BaseDir}", baseDir);
        }
        else
        {
            _logger.LogInformation("Nikon SDK DLLs detected in {BaseDir}", baseDir);
        }
    }

    public void Connect()
    {
        // TODO: initialize MAID, open camera; for now just flag
        Connected = true;
    }

    public void Disconnect()
    {
        // TODO: shutdown MAID
        LiveRunning = false;
        Connected = false;
    }

    public void StartLive()
    {
        // TODO: start MAID live view
        LiveRunning = true;
    }

    public void StopLive()
    {
        // TODO: stop MAID live view
        LiveRunning = false;
    }

    public async Task<string> SimulateShootAsync()
    {
        // Generate a valid JPEG image using ImageSharp (1920x1080 white)
        var ts = DateTime.Now.ToString("yyyyMMdd_HHmmss");
        var name = $"sdk_shoot_{ts}.jpg";
        var path = Path.Combine(WatchDir, name);
        try
        {
            using var img = new Image<Rgba32>(1920, 1080, new Rgba32(255, 255, 255, 255));
            var encoder = new JpegEncoder { Quality = 90 };
            await img.SaveAsJpegAsync(path, encoder);
        }
        catch (Exception e)
        {
            _logger.LogError(e, "Failed to write JPEG to {Path}", path);
            throw;
        }
        _logger.LogInformation("Simulated shoot -> {Path}", path);
        return path;
    }
}
