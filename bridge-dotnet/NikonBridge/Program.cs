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

var app = builder.Build();

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
        if (!sdk.Connected)
        {
            context.Response.StatusCode = StatusCodes.Status409Conflict;
            await context.Response.WriteAsJsonAsync(new { detail = "Not connected. Call /sdk/connect first." });
            return;
        }

        if (maid == null)
        {
            context.Response.StatusCode = StatusCodes.Status500InternalServerError;
            await context.Response.WriteAsJsonAsync(new { detail = "MAID wrapper not initialized" });
            return;
        }

        // Call the real camera shoot function
        var files = maid.Shoot(watchDir);
        await context.Response.WriteAsJsonAsync(new { ok = true, files = files });
    }
    catch (Exception ex)
    {
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
