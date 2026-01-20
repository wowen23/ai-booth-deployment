#pragma once

#include <Windows.h>

namespace NikonMaidWrapper {

    public ref class MaidBridge
    {
    public:
        MaidBridge();
        bool Connect();
        void Disconnect();
        bool StartLive();
        void StopLive();
        array<System::Byte>^ GetLiveFrame();
        array<System::String^>^ Shoot(System::String^ watchDir);
        System::String^ TestLiveViewMode();

        // Autofocus - triggers ContrastAF during live view
        // Returns: 0=success (focused), 1=out of focus, 2=timeout, -1=error
        int Focus();

        // Real-time status check - pings the camera to verify it's responsive
        bool IsConnected();
        bool IsLiveRunning();

        // Read-only properties for cached state (use IsConnected() for real check)
        property bool Connected { bool get() { return connected; } }
        property bool LiveRunning { bool get() { return liveRunning; } }

    private:
        System::IntPtr hNkdPTP;
        System::IntPtr hDnssd;
        System::IntPtr hNkRoyalmile;
        System::IntPtr hMd3Module;
        bool connected;
        bool liveRunning;
        System::String^ md3Path;
        System::IntPtr maidEntry;

        // MAID objects stored as native pointers managed via IntPtr
        System::IntPtr pModuleObj;     // NkMAIDObject* for module
        System::IntPtr pSourceObj;     // NkMAIDObject* for camera (source)
        System::IntPtr pItemObj;       // NkMAIDObject* for item (required for live view)
        unsigned long sourceID;
        unsigned long itemID;

        static System::String^ GetBaseDir();
        bool InitializeModule();
        bool EnumerateAndOpenCamera();
        bool EnumerateAndOpenItem();
        long CallMAID(void* pObject, unsigned long cmd, unsigned long param, unsigned long dataType, void* data);
    };
}
