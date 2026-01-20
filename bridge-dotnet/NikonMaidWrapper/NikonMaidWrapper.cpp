#include "NikonMaidWrapper.h"
#include <msclr/marshal_cppstd.h>
#include <cstdlib>
#include "Maid3.h"
#include "Maid3d1.h"

using namespace NikonMaidWrapper;
using namespace System;
using namespace System::IO;

// Native MAID state kept at file scope (not inside managed ref class)
static LPMAIDEntryPointProc g_pMAIDEntryPoint = nullptr;
static NkMAIDObject g_moduleObj{};
static NkMAIDObject g_sourceObj{};

// Completion callback structure (matches SDK sample)
struct RefCompletionProc {
    volatile ULONG* pulCount;
    void* pRef;
    NKERROR nResult;
};

// Completion callback - increments counter when operation completes
static void CALLPASCAL CompletionProc_Generic(
    LPNkMAIDObject pObject,
    ULONG ulCommand,
    ULONG ulParam,
    ULONG ulDataType,
    NKPARAM data,
    NKREF refComplete,
    NKERROR nResult)
{
    if (refComplete != NULL) {
        RefCompletionProc* pRef = (RefCompletionProc*)refComplete;
        pRef->nResult = nResult;
        if (pRef->pulCount != NULL) {
            (*pRef->pulCount)++;
        }
    }
}

// IdleLoop - pumps Async until completion callback fires
static bool IdleLoop(LPNkMAIDObject pObject, volatile ULONG* pulCount, ULONG ulEndCount, int maxIterations = 1000)
{
    int iterations = 0;
    while (*pulCount < ulEndCount && iterations < maxIterations) {
        SLONG result = g_pMAIDEntryPoint(pObject, kNkMAIDCommand_Async, 0, kNkMAIDDataType_Null, NULL, NULL, NULL);
        if (result != kNkMAIDResult_NoError && result != kNkMAIDResult_Pending) {
            break;
        }
        Sleep(1);
        iterations++;
    }
    return *pulCount >= ulEndCount;
}

// Flag to signal when LiveViewImageStatus changes (0x8517)
static volatile bool g_liveViewStatusChanged = false;
static volatile ULONG g_lastEventCap = 0;

// EventProc callback for Source object (required by SDK)
static void CALLPASCAL EventProc_Source(NKREF refProc, ULONG ulEvent, NKPARAM data)
{
    // 0x4 = kNkMAIDEvent_CapChange, 0x6 = kNkMAIDEvent_CapChangeValueOnly
    // 0x8517 = kNkMAIDCapability_LiveViewImageStatus
    if ((ulEvent == 0x4 || ulEvent == 0x6) && (ULONG)data == 0x8517) {
        g_liveViewStatusChanged = true;
        g_lastEventCap = (ULONG)data;
    }
    printf("[MAID] EventProc_Source: event=0x%X, data=0x%X\n", ulEvent, (ULONG)data);
}

// ProgressProc callback (required by SDK)
static void CALLPASCAL ProgressProc_Generic(ULONG ulCommand, ULONG ulParam, NKREF refProc, ULONG ulDone, ULONG ulTotal)
{
    // Only log occasionally to avoid spam
    static int count = 0;
    if (count++ % 100 == 0) {
        printf("[MAID] ProgressProc: cmd=0x%X, param=0x%X, done=%lu/%lu\n", ulCommand, ulParam, ulDone, ulTotal);
    }
}

// Set up required callbacks on an object
static bool SetupCallbacks(LPNkMAIDObject pObject)
{
    if (g_pMAIDEntryPoint == nullptr || pObject == nullptr) return false;

    NkMAIDCallback stProc;
    SLONG result;

    // Set EventProc
    stProc.refProc = (NKREF)pObject;
    stProc.pProc = (LPNKFUNC)EventProc_Source;
    result = g_pMAIDEntryPoint(pObject, kNkMAIDCommand_CapSet, kNkMAIDCapability_EventProc,
                                kNkMAIDDataType_CallbackPtr, (NKPARAM)&stProc, NULL, NULL);
    printf("[MAID] SetupCallbacks: EventProc set result=%ld\n", result);

    // Set ProgressProc
    stProc.pProc = (LPNKFUNC)ProgressProc_Generic;
    result = g_pMAIDEntryPoint(pObject, kNkMAIDCommand_CapSet, kNkMAIDCapability_ProgressProc,
                                kNkMAIDDataType_CallbackPtr, (NKPARAM)&stProc, NULL, NULL);
    printf("[MAID] SetupCallbacks: ProgressProc set result=%ld\n", result);

    return true;
}

static std::wstring FormatWin32Error(DWORD err)
{
    LPWSTR buf = nullptr;
    DWORD n = ::FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        nullptr,
        err,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPWSTR)&buf,
        0,
        nullptr);
    std::wstring msg = (n && buf) ? std::wstring(buf, n) : L"";
    if (buf) ::LocalFree(buf);
    return msg;
}

MaidBridge::MaidBridge()
{
    try {
        hNkdPTP = IntPtr::Zero;
        hDnssd = IntPtr::Zero;
        hNkRoyalmile = IntPtr::Zero;
        hMd3Module = IntPtr::Zero;
        connected = false;
        liveRunning = false;
        md3Path = nullptr;
        maidEntry = IntPtr::Zero;
        pModuleObj = IntPtr::Zero;
        pSourceObj = IntPtr::Zero;
        pItemObj = IntPtr::Zero;
        sourceID = 0;
        itemID = 0;
        g_pMAIDEntryPoint = nullptr; // Ensure it starts null
    }
    catch (Exception^ ex) {
        throw gcnew Exception("MaidBridge constructor failed: " + ex->Message);
    }
}

String^ MaidBridge::GetBaseDir()
{
    // Where NikonBridge.exe and Nikon DLLs live
    return AppDomain::CurrentDomain->BaseDirectory;
}

bool MaidBridge::Connect()
{
    if (connected) return true;

    try {
        Console::WriteLine("[MAID] Connect() starting...");

        auto baseDir = GetBaseDir();
        Console::WriteLine("[MAID] BaseDir: " + baseDir);

        if (baseDir == nullptr) {
            throw gcnew Exception("GetBaseDir() returned null");
        }

        auto p1 = Path::Combine(baseDir, "NkdPTP.dll");
        auto p2 = Path::Combine(baseDir, "dnssd.dll");
        auto p3 = Path::Combine(baseDir, "NkRoyalmile.dll");
        auto md3 = Path::Combine(baseDir, "Type0029.md3");

        Console::WriteLine("[MAID] DLL paths resolved");

        auto s1 = msclr::interop::marshal_as<std::wstring>(p1);
        auto s2 = msclr::interop::marshal_as<std::wstring>(p2);
        auto s3 = msclr::interop::marshal_as<std::wstring>(p3);
        auto sMd3 = msclr::interop::marshal_as<std::wstring>(md3);

        Console::WriteLine("[MAID] Loading NkdPTP.dll...");
        HMODULE h1 = ::LoadLibraryW(s1.c_str());
        if (!h1) {
            DWORD err = ::GetLastError();
            auto w = L"Failed to load NkdPTP.dll (" + std::to_wstring(err) + L"): " + FormatWin32Error(err);
            throw gcnew Exception(gcnew System::String(w.c_str()));
        }
        Console::WriteLine("[MAID] Loading dnssd.dll...");
        HMODULE h2 = ::LoadLibraryW(s2.c_str());
        if (!h2) {
            DWORD err = ::GetLastError();
            ::FreeLibrary(h1);
            auto w = L"Failed to load dnssd.dll (" + std::to_wstring(err) + L"): " + FormatWin32Error(err);
            throw gcnew Exception(gcnew System::String(w.c_str()));
        }
        Console::WriteLine("[MAID] Loading NkRoyalmile.dll...");
        HMODULE h3 = ::LoadLibraryW(s3.c_str());
        if (!h3) {
            DWORD err = ::GetLastError();
            ::FreeLibrary(h2); ::FreeLibrary(h1);
            auto w = L"Failed to load NkRoyalmile.dll (" + std::to_wstring(err) + L"): " + FormatWin32Error(err);
            throw gcnew Exception(gcnew System::String(w.c_str()));
        }
        this->hNkdPTP = IntPtr(h1);
        this->hDnssd = IntPtr(h2);
        this->hNkRoyalmile = IntPtr(h3);
        Console::WriteLine("[MAID] Support DLLs loaded successfully");

        // Verify MAID module exists (loading via MAID API will follow in next step)
        Console::WriteLine("[MAID] Checking for Type0029.md3...");
        if (!File::Exists(md3)) { Disconnect(); throw gcnew Exception("Missing Type0029.md3 in bridge output folder"); }
        md3Path = md3;

        // Load Type0029.md3 and resolve MAID entry point
        Console::WriteLine("[MAID] Loading Type0029.md3...");
        HMODULE hMd3 = ::LoadLibraryW(sMd3.c_str());
        if (!hMd3) {
            DWORD err = ::GetLastError();
            Disconnect();
            auto w = L"Failed to load Type0029.md3 (" + std::to_wstring(err) + L"): " + FormatWin32Error(err);
            throw gcnew Exception(gcnew System::String(w.c_str()));
        }
        Console::WriteLine("[MAID] Resolving MAIDEntryPoint...");
        FARPROC p = ::GetProcAddress(hMd3, "MAIDEntryPoint");
        if (!p) {
            Disconnect();
            throw gcnew Exception("MAIDEntryPoint function not found in Type0029.md3. The SDK module file may be corrupted.");
        }

        g_pMAIDEntryPoint = reinterpret_cast<LPMAIDEntryPointProc>(p);
        this->hMd3Module = IntPtr(hMd3);
        this->maidEntry = IntPtr(p);

        // Verify entry point is valid before proceeding
        if (g_pMAIDEntryPoint == nullptr) {
            Disconnect();
            throw gcnew Exception("MAID entry point is null after initialization");
        }
        Console::WriteLine("[MAID] MAID entry point resolved successfully");

        // Initialize and open the MAID module
        Console::WriteLine("[MAID] Initializing MAID module...");
        if (!InitializeModule()) {
            Disconnect();
            throw gcnew Exception("Failed to initialize MAID module");
        }
        Console::WriteLine("[MAID] MAID module initialized");

        // Enumerate and open first available camera
        Console::WriteLine("[MAID] Enumerating and opening camera...");
        if (!EnumerateAndOpenCamera()) {
            Disconnect();
            throw gcnew Exception("Failed to find or open camera");
        }
        Console::WriteLine("[MAID] Camera opened successfully");

        // Try to enumerate and open item (optional - Z6 II may not have items without photos on card)
        Console::WriteLine("[MAID] Attempting to enumerate items...");
        try {
            if (EnumerateAndOpenItem()) {
                Console::WriteLine("[MAID] Item opened successfully - will use Item for live view");
            }
        }
        catch (Exception^ ex) {
            Console::WriteLine("[MAID] No items available (this is normal): " + ex->Message);
            Console::WriteLine("[MAID] Will use Source object for live view instead");
        }

        connected = true;
        Console::WriteLine("[MAID] Connect() completed successfully");
        return true;
    }
    catch (Exception^ ex) {
        // Re-throw with more context
        throw gcnew Exception("Connect() failed: " + ex->Message, ex);
    }
}

// Helper to call MAID entry point
long MaidBridge::CallMAID(void* pObject, unsigned long cmd, unsigned long param, unsigned long dataType, void* data)
{
    if (g_pMAIDEntryPoint == nullptr) return kNkMAIDResult_UnexpectedError;
    return g_pMAIDEntryPoint(static_cast<LPNkMAIDObject>(pObject), cmd, param, dataType, (NKPARAM)data, NULL, NULL);
}

// Initialize MAID module object
bool MaidBridge::InitializeModule()
{
    Console::WriteLine("[MAID] InitializeModule() starting...");

    // Double-check entry point is valid
    if (g_pMAIDEntryPoint == nullptr) {
        throw gcnew Exception("Cannot initialize MAID module: entry point is null");
    }

    // Allocate module object
    Console::WriteLine("[MAID] Allocating module object...");
    NkMAIDObject* pMod = new NkMAIDObject();
    if (!pMod) {
        throw gcnew Exception("Failed to allocate module object");
    }
    memset(pMod, 0, sizeof(NkMAIDObject));
    Console::WriteLine("[MAID] Module object allocated");

    // Open module (parent is NULL for module object, ID is 0)
    SLONG result = g_pMAIDEntryPoint(NULL, kNkMAIDCommand_Open, 0, kNkMAIDDataType_ObjectPtr, (NKPARAM)pMod, NULL, NULL);
    if (result != kNkMAIDResult_NoError) {
        delete pMod;
        throw gcnew Exception(String::Format("Failed to open MAID module, error code: {0}", result));
    }

    pModuleObj = IntPtr(pMod);

    // Try to set module mode to Controller (optional - not all modules support this)
    ULONG mode = kNkMAIDModuleMode_Controller;
    result = g_pMAIDEntryPoint(pMod, kNkMAIDCommand_CapSet, kNkMAIDCapability_ModuleMode,
                      kNkMAIDDataType_Unsigned, (NKPARAM)&mode, NULL, NULL);

    // Ignore error if ModuleMode capability is not supported (-127 = kNkMAIDResult_NotSupported)
    // The module will work without explicitly setting this
    if (result != kNkMAIDResult_NoError && result != -127) {
        throw gcnew Exception(String::Format("Failed to set module mode, error code: {0}", result));
    }

    return true;
}

// Enumerate cameras and open the first one
bool MaidBridge::EnumerateAndOpenCamera()
{
    Console::WriteLine("[MAID] EnumerateAndOpenCamera() starting...");

    if (pModuleObj == IntPtr::Zero) {
        throw gcnew Exception("Module object is null");
    }
    NkMAIDObject* pMod = static_cast<NkMAIDObject*>(pModuleObj.ToPointer());

    if (pMod == nullptr) {
        throw gcnew Exception("Module object pointer is null after cast");
    }

    Console::WriteLine(String::Format("[MAID] Module object pointer: 0x{0:X}", (unsigned long long)pMod));

    // IMPORTANT: Call EnumChildren first to force SDK to scan for connected cameras
    // Without this, the SDK may return stale/cached camera list
    Console::WriteLine("[MAID] Calling EnumChildren to refresh camera list...");
    SLONG enumResult = g_pMAIDEntryPoint(pMod, kNkMAIDCommand_EnumChildren, 0, kNkMAIDDataType_Null, NULL, NULL, NULL);
    Console::WriteLine(String::Format("[MAID] EnumChildren returned: {0}", enumResult));

    // Don't fail on EnumChildren error - some SDK configs don't require it
    // We'll check the actual camera count next
    if (enumResult != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] Warning: EnumChildren returned {0}, continuing anyway...", enumResult));
    }

    // Get list of children (cameras)
    Console::WriteLine("[MAID] Getting camera list (Children capability)...");
    NkMAIDEnum stEnum;
    memset(&stEnum, 0, sizeof(NkMAIDEnum));

    SLONG result = kNkMAIDResult_UnexpectedError;
    try {
        Console::WriteLine("[MAID] Calling CapGet for Children...");
        result = g_pMAIDEntryPoint(pMod, kNkMAIDCommand_CapGet, kNkMAIDCapability_Children,
                          kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL);
        Console::WriteLine(String::Format("[MAID] CapGet returned: {0}", result));
    }
    catch (System::Exception^ ex) {
        throw gcnew Exception("Exception during CapGet Children: " + ex->Message);
    }
    catch (...) {
        throw gcnew Exception("Native exception during CapGet Children - SDK may have encountered a null pointer");
    }

    if (result != kNkMAIDResult_NoError) {
        throw gcnew Exception(String::Format("Failed to get camera list after enumeration, error code: {0}. Camera may not be connected or in wrong USB mode.", result));
    }

    Console::WriteLine(String::Format("[MAID] stEnum.ulElements: {0}", stEnum.ulElements));
    Console::WriteLine(String::Format("[MAID] stEnum.wPhysicalBytes: {0}", stEnum.wPhysicalBytes));

    if (stEnum.ulElements == 0) {
        throw gcnew Exception("No cameras found. Make sure your Nikon Z6 II is:\n1. Connected via USB\n2. Powered on\n3. Set to PC connection mode (not MTP/PTP)\n4. Not in use by other software (Camera Control Pro, etc.)");
    }

    // Allocate memory for the camera ID array (SDK pattern requires us to allocate)
    Console::WriteLine("[MAID] Allocating buffer for camera IDs...");
    stEnum.pData = malloc(stEnum.ulElements * stEnum.wPhysicalBytes);
    if (stEnum.pData == nullptr) {
        throw gcnew Exception("Failed to allocate memory for camera ID array");
    }

    // Now get the actual array data using CapGetArray
    Console::WriteLine("[MAID] Calling CapGetArray to retrieve camera IDs...");
    result = g_pMAIDEntryPoint(pMod, kNkMAIDCommand_CapGetArray, kNkMAIDCapability_Children,
                      kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL);
    Console::WriteLine(String::Format("[MAID] CapGetArray returned: {0}", result));

    if (result != kNkMAIDResult_NoError) {
        free(stEnum.pData);
        throw gcnew Exception(String::Format("Failed to get camera ID array, error code: {0}", result));
    }

    // Get first camera ID
    Console::WriteLine("[MAID] Getting first camera ID from enum data...");
    ULONG* pSourceIDs = static_cast<ULONG*>(stEnum.pData);
    sourceID = pSourceIDs[0];
    Console::WriteLine(String::Format("[MAID] First camera ID: {0}", sourceID));

    // Free the allocated buffer
    free(stEnum.pData);

    // Allocate and open source object for first camera
    Console::WriteLine("[MAID] Allocating source object for camera...");
    NkMAIDObject* pSrc = new NkMAIDObject();
    if (!pSrc) {
        throw gcnew Exception("Failed to allocate source object");
    }
    memset(pSrc, 0, sizeof(NkMAIDObject));

    Console::WriteLine(String::Format("[MAID] Opening camera with ID {0}...", sourceID));
    result = g_pMAIDEntryPoint(pMod, kNkMAIDCommand_Open, sourceID, kNkMAIDDataType_ObjectPtr, (NKPARAM)pSrc, NULL, NULL);
    Console::WriteLine(String::Format("[MAID] Camera open returned: {0}", result));

    if (result != kNkMAIDResult_NoError) {
        delete pSrc;
        throw gcnew Exception(String::Format("Failed to open camera, error code: {0}", result));
    }

    pSourceObj = IntPtr(pSrc);
    Console::WriteLine("[MAID] Camera opened successfully");

    // Set up required callbacks on source object (EventProc, ProgressProc)
    Console::WriteLine("[MAID] Setting up callbacks on source object...");
    SetupCallbacks(pSrc);

    return true;
}

// Enumerate items and open the first one (required for live view on Z6 II)
bool MaidBridge::EnumerateAndOpenItem()
{
    Console::WriteLine("[MAID] EnumerateAndOpenItem() starting...");

    if (pSourceObj == IntPtr::Zero) {
        throw gcnew Exception("Source object is null");
    }
    NkMAIDObject* pSrc = static_cast<NkMAIDObject*>(pSourceObj.ToPointer());

    if (pSrc == nullptr) {
        throw gcnew Exception("Source object pointer is null after cast");
    }

    // Get list of items (children of source)
    Console::WriteLine("[MAID] Getting item list (Children capability)...");
    NkMAIDEnum stEnum;
    memset(&stEnum, 0, sizeof(NkMAIDEnum));

    SLONG result = kNkMAIDResult_UnexpectedError;
    try {
        Console::WriteLine("[MAID] Calling CapGet for Children...");
        result = g_pMAIDEntryPoint(pSrc, kNkMAIDCommand_CapGet, kNkMAIDCapability_Children,
                          kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL);
        Console::WriteLine(String::Format("[MAID] CapGet returned: {0}", result));
    }
    catch (System::Exception^ ex) {
        throw gcnew Exception("Exception during CapGet Children: " + ex->Message);
    }
    catch (...) {
        throw gcnew Exception("Native exception during CapGet Children");
    }

    if (result != kNkMAIDResult_NoError) {
        throw gcnew Exception(String::Format("Failed to get item list, error code: {0}. Camera may not have items available.", result));
    }

    Console::WriteLine(String::Format("[MAID] stEnum.ulElements: {0}", stEnum.ulElements));
    Console::WriteLine(String::Format("[MAID] stEnum.wPhysicalBytes: {0}", stEnum.wPhysicalBytes));

    if (stEnum.ulElements == 0) {
        throw gcnew Exception("No items found. The camera may need to be in a specific mode.");
    }

    // Allocate memory for the item ID array
    Console::WriteLine("[MAID] Allocating buffer for item IDs...");
    stEnum.pData = malloc(stEnum.ulElements * stEnum.wPhysicalBytes);
    if (stEnum.pData == nullptr) {
        throw gcnew Exception("Failed to allocate memory for item ID array");
    }

    // Now get the actual array data using CapGetArray
    Console::WriteLine("[MAID] Calling CapGetArray to retrieve item IDs...");
    result = g_pMAIDEntryPoint(pSrc, kNkMAIDCommand_CapGetArray, kNkMAIDCapability_Children,
                      kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL);
    Console::WriteLine(String::Format("[MAID] CapGetArray returned: {0}", result));

    if (result != kNkMAIDResult_NoError) {
        free(stEnum.pData);
        throw gcnew Exception(String::Format("Failed to get item ID array, error code: {0}", result));
    }

    // Get first item ID
    Console::WriteLine("[MAID] Getting first item ID from enum data...");
    ULONG* pItemIDs = static_cast<ULONG*>(stEnum.pData);
    itemID = pItemIDs[0];
    Console::WriteLine(String::Format("[MAID] First item ID: {0}", itemID));

    // Free the allocated buffer
    free(stEnum.pData);

    // Allocate and open item object for first item
    Console::WriteLine("[MAID] Allocating item object...");
    NkMAIDObject* pItem = new NkMAIDObject();
    if (!pItem) {
        throw gcnew Exception("Failed to allocate item object");
    }
    memset(pItem, 0, sizeof(NkMAIDObject));

    Console::WriteLine(String::Format("[MAID] Opening item with ID {0}...", itemID));
    result = g_pMAIDEntryPoint(pSrc, kNkMAIDCommand_Open, itemID, kNkMAIDDataType_ObjectPtr, (NKPARAM)pItem, NULL, NULL);
    Console::WriteLine(String::Format("[MAID] Item open returned: {0}", result));

    if (result != kNkMAIDResult_NoError) {
        delete pItem;
        throw gcnew Exception(String::Format("Failed to open item, error code: {0}", result));
    }

    pItemObj = IntPtr(pItem);
    Console::WriteLine("[MAID] Item opened successfully");

    return true;
}

void MaidBridge::Disconnect()
{
    Console::WriteLine("[MAID] Disconnect() called");

    // Close item object
    if (pItemObj != IntPtr::Zero) {
        NkMAIDObject* pItem = static_cast<NkMAIDObject*>(pItemObj.ToPointer());
        CallMAID(pItem, kNkMAIDCommand_Close, 0, 0, NULL);
        delete pItem;
        pItemObj = IntPtr::Zero;
        Console::WriteLine("[MAID] Closed item object");
    }

    // Close source object
    if (pSourceObj != IntPtr::Zero) {
        NkMAIDObject* pSrc = static_cast<NkMAIDObject*>(pSourceObj.ToPointer());
        CallMAID(pSrc, kNkMAIDCommand_Close, 0, 0, NULL);
        delete pSrc;
        pSourceObj = IntPtr::Zero;
        Console::WriteLine("[MAID] Closed source object");
    }

    // Close module object
    if (pModuleObj != IntPtr::Zero) {
        NkMAIDObject* pMod = static_cast<NkMAIDObject*>(pModuleObj.ToPointer());
        CallMAID(pMod, kNkMAIDCommand_Close, 0, 0, NULL);
        delete pMod;
        pModuleObj = IntPtr::Zero;
        Console::WriteLine("[MAID] Closed module object");
    }

    // Unload DLLs to fully reset SDK state
    // This is necessary when camera is power cycled - SDK internal handles become invalid
    Console::WriteLine("[MAID] Unloading DLLs to reset SDK state...");
    if (hMd3Module != IntPtr::Zero) {
        ::FreeLibrary(static_cast<HMODULE>(hMd3Module.ToPointer()));
        hMd3Module = IntPtr::Zero;
    }
    g_pMAIDEntryPoint = nullptr;
    if (hNkRoyalmile != IntPtr::Zero) {
        ::FreeLibrary(static_cast<HMODULE>(hNkRoyalmile.ToPointer()));
        hNkRoyalmile = IntPtr::Zero;
    }
    if (hDnssd != IntPtr::Zero) {
        ::FreeLibrary(static_cast<HMODULE>(hDnssd.ToPointer()));
        hDnssd = IntPtr::Zero;
    }
    if (hNkdPTP != IntPtr::Zero) {
        ::FreeLibrary(static_cast<HMODULE>(hNkdPTP.ToPointer()));
        hNkdPTP = IntPtr::Zero;
    }

    // Small delay to let Windows fully release USB handles
    Sleep(500);

    connected = false;
    liveRunning = false;
    Console::WriteLine("[MAID] Disconnect() complete");
}

// Real-time check if camera is actually connected and responding
bool MaidBridge::IsConnected()
{
    // Quick check of cached state first
    if (!connected) {
        return false;
    }

    // Check if we have valid objects
    if (pSourceObj == IntPtr::Zero || g_pMAIDEntryPoint == nullptr) {
        Console::WriteLine("[MAID] IsConnected: No source object or entry point - marking disconnected");
        connected = false;
        liveRunning = false;
        return false;
    }

    NkMAIDObject* pSource = static_cast<NkMAIDObject*>(pSourceObj.ToPointer());

    // Try to query a simple capability to verify camera is responsive
    // We'll use GetCapCount which should always work on a valid source
    ULONG capCount = 0;
    SLONG result = CallMAID(pSource, kNkMAIDCommand_GetCapCount, 0, kNkMAIDDataType_UnsignedPtr, &capCount);

    if (result != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] IsConnected: GetCapCount failed with error {0} - camera disconnected", result));
        connected = false;
        liveRunning = false;
        return false;
    }

    // Camera responded - it's connected
    return true;
}

// Real-time check if live view is actually running
bool MaidBridge::IsLiveRunning()
{
    // Quick check of cached state first
    if (!liveRunning || !connected) {
        return false;
    }

    // Verify camera is still connected
    if (!IsConnected()) {
        return false;
    }

    NkMAIDObject* pSource = static_cast<NkMAIDObject*>(pSourceObj.ToPointer());

    // Check LiveViewStatus capability to see if live view is actually running
    NkMAIDEnum stEnum;
    memset(&stEnum, 0, sizeof(NkMAIDEnum));
    SLONG result = CallMAID(pSource, kNkMAIDCommand_CapGet, kNkMAIDCapability_LiveViewStatus,
                            kNkMAIDDataType_EnumPtr, &stEnum);

    if (result != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] IsLiveRunning: LiveViewStatus query failed with error {0}", result));
        liveRunning = false;
        return false;
    }

    // Check if live view is actually on (value 3 = Remote Live View)
    // Values: 0=OFF, 1=ON, 2=ON_Menu, 3=ON_RemoteLV, 4=ON_CameraLV
    if (stEnum.ulValue == 0) {
        Console::WriteLine("[MAID] IsLiveRunning: LiveViewStatus is 0 (OFF) - marking stopped");
        liveRunning = false;
        return false;
    }

    return true;
}

bool MaidBridge::StartLive()
{
    Console::WriteLine("[MAID] StartLive() called");

    if (!connected) {
        Console::WriteLine("[MAID] StartLive failed: not connected");
        return false;
    }

    if (pSourceObj == IntPtr::Zero) {
        Console::WriteLine("[MAID] StartLive failed: no source object");
        return false;
    }

    NkMAIDObject* pSource = static_cast<NkMAIDObject*>(pSourceObj.ToPointer());

    // First, enumerate what capabilities are actually available
    Console::WriteLine("[MAID] Enumerating Source capabilities...");
    ULONG capCount = 0;
    SLONG result = CallMAID(pSource, kNkMAIDCommand_GetCapCount, 0, kNkMAIDDataType_UnsignedPtr, &capCount);
    Console::WriteLine(String::Format("[MAID] Source has {0} capabilities", capCount));

    NkMAIDCapInfo liveViewStatusInfo = {};
    if (capCount > 0) {
        // Look for live view related capabilities
        Console::WriteLine("[MAID] Searching for live view capabilities...");
        bool foundLiveViewImage = false;
        bool foundLiveViewSelector = false;
        bool foundLiveViewStatus = false;

        NkMAIDCapInfo* pCapInfo = new NkMAIDCapInfo[capCount];
        result = CallMAID(pSource, kNkMAIDCommand_GetCapInfo, capCount, kNkMAIDDataType_CapInfoPtr, pCapInfo);

        if (result == kNkMAIDResult_NoError) {
            for (ULONG i = 0; i < capCount; i++) {
                if (pCapInfo[i].ulID == kNkMAIDCapability_GetLiveViewImage) {
                    foundLiveViewImage = true;
                    Console::WriteLine(String::Format("[MAID] Found GetLiveViewImage at index {0}", i));
                    Console::WriteLine(String::Format("[MAID]   Type={0}, Operations=0x{1:X} (Get=0x2, GetArray=0x8)",
                                      pCapInfo[i].ulType, pCapInfo[i].ulOperations));
                }
                if (pCapInfo[i].ulID == kNkMAIDCapability_LiveViewSelector) {
                    foundLiveViewSelector = true;
                    Console::WriteLine(String::Format("[MAID] Found LiveViewSelector at index {0}", i));
                }
                if (pCapInfo[i].ulID == kNkMAIDCapability_LiveViewStatus) {
                    foundLiveViewStatus = true;
                    liveViewStatusInfo = pCapInfo[i];
                    Console::WriteLine(String::Format("[MAID] Found LiveViewStatus at index {0}", i));
                    Console::WriteLine(String::Format("[MAID]   Type={0}, Operations={1}, Visibility={2}",
                                      pCapInfo[i].ulType, pCapInfo[i].ulOperations, pCapInfo[i].ulVisibility));
                }
            }
        }
        delete[] pCapInfo;

        Console::WriteLine(String::Format("[MAID] Live view caps: GetImage={0}, Selector={1}, Status={2}",
                          foundLiveViewImage, foundLiveViewSelector, foundLiveViewStatus));
    }

    // Check if the capability is an enum and what values are valid
    if (liveViewStatusInfo.ulType == kNkMAIDCapType_Enum) {
        Console::WriteLine("[MAID] LiveViewStatus is an Enum type, getting valid values...");
        NkMAIDEnum stEnum;
        memset(&stEnum, 0, sizeof(NkMAIDEnum));
        result = CallMAID(pSource, kNkMAIDCommand_CapGet, kNkMAIDCapability_LiveViewStatus,
                          kNkMAIDDataType_EnumPtr, &stEnum);
        if (result == kNkMAIDResult_NoError && stEnum.pData != nullptr && stEnum.ulElements > 0) {
            Console::WriteLine(String::Format("[MAID] Valid LiveViewStatus values ({0}):", stEnum.ulElements));
            ULONG* pValues = (ULONG*)stEnum.pData;
            for (ULONG i = 0; i < stEnum.ulElements; i++) {
                Console::WriteLine(String::Format("[MAID]   [{0}] = {1}", i, pValues[i]));
            }
        } else {
            Console::WriteLine(String::Format("[MAID] Failed to enumerate: {0}", result));
        }
    }

    // Check LiveViewSelector first - this might need to be set to photo mode
    Console::WriteLine("[MAID] Checking LiveViewSelector...");
    ULONG selector = 99;
    result = CallMAID(pSource, kNkMAIDCommand_CapGet, kNkMAIDCapability_LiveViewSelector,
                      kNkMAIDDataType_Unsigned, &selector);
    Console::WriteLine(String::Format("[MAID] LiveViewSelector: result={0}, value={1} (0=photo, 1=movie)", result, selector));

    if (result == kNkMAIDResult_NoError && selector != 0) {
        Console::WriteLine("[MAID] Switching to photo live view mode (0)...");
        selector = 0;
        result = CallMAID(pSource, kNkMAIDCommand_CapSet, kNkMAIDCapability_LiveViewSelector,
                          kNkMAIDDataType_Unsigned, (void*)(NKPARAM)selector);  // Pass value as NKPARAM
        Console::WriteLine(String::Format("[MAID] LiveViewSelector Set: result={0}", result));
    }

    // FIRST: Check LiveViewProhibit before attempting to start live view
    Console::WriteLine("[MAID] Checking LiveViewProhibit...");
    ULONG prohibit = 0;
    result = CallMAID(pSource, kNkMAIDCommand_CapGet, kNkMAIDCapability_LiveViewProhibit,
                      kNkMAIDDataType_Unsigned, &prohibit);
    Console::WriteLine(String::Format("[MAID] LiveViewProhibit CapGet: result={0}, value=0x{1:X8}", result, prohibit));

    if (result == kNkMAIDResult_NoError && prohibit != 0) {
        Console::WriteLine("[MAID] Live view is PROHIBITED! Reasons:");
        if (prohibit & 0x10000000) Console::WriteLine("[MAID]   - 0x10000000: Lens/mount adapter issue or needs firmware update");
        if (prohibit & 0x00020000) Console::WriteLine("[MAID]   - 0x00020000: High temperature");
        if (prohibit & 0x00008000) Console::WriteLine("[MAID]   - 0x00008000: During photo shooting");
        if (prohibit & 0x00000100) Console::WriteLine("[MAID]   - 0x00000100: Battery shortage");
        if (prohibit & 0x00000004) Console::WriteLine("[MAID]   - 0x00000004: Sequence error");
        Console::WriteLine("[MAID] Cannot start live view - resolve these issues first!");
        // Continue anyway to get diagnostic info
    } else if (result == kNkMAIDResult_NoError) {
        Console::WriteLine("[MAID] Live view is allowed (no prohibitions)");
    }

    // Check CURRENT LiveViewStatus value
    // Try as Enum first since CapGet with Unsigned is failing with -126
    Console::WriteLine("[MAID] Checking current LiveViewStatus (trying Enum type)...");
    NkMAIDEnum stEnum;
    memset(&stEnum, 0, sizeof(NkMAIDEnum));
    result = CallMAID(pSource, kNkMAIDCommand_CapGet, kNkMAIDCapability_LiveViewStatus,
                      kNkMAIDDataType_EnumPtr, &stEnum);
    Console::WriteLine(String::Format("[MAID] LiveViewStatus Enum CapGet: result={0}", result));

    ULONG currentStatus = 99;
    if (result == kNkMAIDResult_NoError && stEnum.pData != nullptr && stEnum.ulElements > 0) {
        currentStatus = stEnum.ulValue;  // Current value
        Console::WriteLine(String::Format("[MAID] Current LiveViewStatus: {0} (0=OFF,1=ON,2=ON_Menu,3=ON_RemoteLV,4=ON_CameraLV)", currentStatus));
        Console::WriteLine(String::Format("[MAID] Valid LiveViewStatus values ({0}):", stEnum.ulElements));
        ULONG* pValues = (ULONG*)stEnum.pData;
        for (ULONG i = 0; i < stEnum.ulElements; i++) {
            Console::WriteLine(String::Format("[MAID]   [{0}] = {1}", i, pValues[i]));
        }
    } else {
        Console::WriteLine(String::Format("[MAID] Could not read LiveViewStatus: error {0}", result));
    }

    // ALWAYS force a clean live view start by stopping first, then starting
    // This handles stale state after camera disconnect/reconnect
    Console::WriteLine("[MAID] Forcing clean live view start: setting LiveViewStatus to 0 (OFF) first...");
    ULONG stopStatus = 0;
    result = CallMAID(pSource, kNkMAIDCommand_CapSet, kNkMAIDCapability_LiveViewStatus,
                      kNkMAIDDataType_Unsigned, (void*)(NKPARAM)stopStatus);
    Console::WriteLine(String::Format("[MAID] LiveViewStatus Set(0): result={0}", result));

    // Small delay to let camera process the stop
    Sleep(100);

    // Now set to Remote Live View mode
    Console::WriteLine("[MAID] Setting LiveViewStatus to 3 (Remote Live View)...");
    ULONG startStatus = 3;  // kNkMAIDLiveViewStatus_ON_RemoteLV
    result = CallMAID(pSource, kNkMAIDCommand_CapSet, kNkMAIDCapability_LiveViewStatus,
                      kNkMAIDDataType_Unsigned, (void*)(NKPARAM)startStatus);
    Console::WriteLine(String::Format("[MAID] LiveViewStatus Set(3): result={0}", result));

    if (result != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] Warning: Could not set LiveViewStatus: error {0}", result));
    }

    // Give camera a moment to process the live view state change
    Console::WriteLine("[MAID] Waiting for camera to initialize live view...");
    Sleep(200);

    // Pump Async to let camera process
    for (int i = 0; i < 5; i++) {
        g_pMAIDEntryPoint(pSource, kNkMAIDCommand_Async, 0, kNkMAIDDataType_Null, NULL, NULL, NULL);
        Sleep(20);
    }

    // Don't try to get a test frame here - it may interfere with subsequent GetLiveFrame calls
    // Just mark live view as running and let GetLiveFrame handle actual frame acquisition
    Console::WriteLine("[MAID] Live view mode set. Marking as running - GetLiveFrame will fetch actual frames.");
    liveRunning = true;
    return true;
}

void MaidBridge::StopLive()
{
    Console::WriteLine("[MAID] StopLive() called");

    if (!connected || pSourceObj == IntPtr::Zero) {
        Console::WriteLine("[MAID] StopLive: not connected or no source");
        return;
    }

    NkMAIDObject* pSource = static_cast<NkMAIDObject*>(pSourceObj.ToPointer());

    // Set LiveViewStatus to 0 (OFF) to stop live view
    ULONG status = 0;
    SLONG result = CallMAID(pSource, kNkMAIDCommand_CapSet, kNkMAIDCapability_LiveViewStatus,
                            kNkMAIDDataType_Unsigned, (void*)(NKPARAM)status);  // Pass value as NKPARAM
    Console::WriteLine(String::Format("[MAID] StopLive CapSet(0) returned: {0}", result));

    liveRunning = false;
}

array<System::Byte>^ MaidBridge::GetLiveFrame()
{
    if (!liveRunning || pSourceObj == IntPtr::Zero || g_pMAIDEntryPoint == nullptr) {
        return gcnew array<System::Byte>(0);
    }

    NkMAIDObject* pSource = static_cast<NkMAIDObject*>(pSourceObj.ToPointer());
    static int frameAttempts = 0;
    frameAttempts++;

    // === PHASE 1: Get array metadata with completion callback ===
    NkMAIDArray stArray;
    memset(&stArray, 0, sizeof(NkMAIDArray));

    volatile ULONG ulCount1 = 0;
    RefCompletionProc refProc1;
    refProc1.pulCount = &ulCount1;
    refProc1.pRef = NULL;
    refProc1.nResult = 0;

    SLONG result1 = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGet, kNkMAIDCapability_GetLiveViewImage,
                                       kNkMAIDDataType_ArrayPtr, (NKPARAM)&stArray,
                                       (LPNKFUNC)CompletionProc_Generic, (NKREF)&refProc1);

    // Wait for Phase 1 completion
    IdleLoop(pSource, &ulCount1, 1, 200);

    if (result1 != 0 || stArray.ulElements == 0) {
        if (frameAttempts <= 5) {
            Console::WriteLine(String::Format("[MAID] GetLiveFrame #{0}: Phase1 failed, result={1}, elements={2}",
                frameAttempts, result1, stArray.ulElements));
        }
        return gcnew array<System::Byte>(0);
    }

    // === PHASE 2: Allocate buffer and get actual data with CapGetArray ===
    ULONG bufSize = stArray.ulElements * (stArray.wPhysicalBytes > 0 ? stArray.wPhysicalBytes : 1);
    stArray.pData = malloc(bufSize);
    if (stArray.pData == nullptr) {
        return gcnew array<System::Byte>(0);
    }

    volatile ULONG ulCount2 = 0;
    RefCompletionProc refProc2;
    refProc2.pulCount = &ulCount2;
    refProc2.pRef = NULL;
    refProc2.nResult = 0;

    SLONG result2 = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGetArray, kNkMAIDCapability_GetLiveViewImage,
                                       kNkMAIDDataType_ArrayPtr, (NKPARAM)&stArray,
                                       (LPNKFUNC)CompletionProc_Generic, (NKREF)&refProc2);

    // Wait for Phase 2 completion - THIS IS WHERE DATA ARRIVES
    IdleLoop(pSource, &ulCount2, 1, 200);

    unsigned char* pData = static_cast<unsigned char*>(stArray.pData);

    if (frameAttempts <= 10) {
        Console::WriteLine(String::Format("[MAID] GetLiveFrame #{0}: Phase2 result={1}, callback={2}, @512: {3:X2} {4:X2}",
            frameAttempts, result2, ulCount2, pData[512], pData[513]));
    }

    // Check for valid JPEG data at offset 512 (after header)
    if (pData[512] == 0xFF && pData[513] == 0xD8) {
        ULONG headerSize = 512;
        ULONG jpegSize = stArray.ulElements - headerSize;
        array<System::Byte>^ jpegData = gcnew array<System::Byte>(jpegSize);
        System::Runtime::InteropServices::Marshal::Copy(IntPtr(pData + headerSize), jpegData, 0, jpegSize);
        free(stArray.pData);
        return jpegData;
    }

    free(stArray.pData);
    return gcnew array<System::Byte>(0);
}

// Helper structure for capture context (native, not managed)
struct CaptureContext {
    volatile bool captureComplete;
    volatile SLONG newItemID;
    LPVOID imageBuffer;
    ULONG bufferSize;
    ULONG fileDataType;  // kNkMAIDFileDataType_JPEG, etc.
    char watchDirPath[512];
    char savedFilePath[512];
    volatile bool downloadComplete;
    volatile NKERROR lastError;
};

// Global capture context (simplified - in production use better lifecycle management)
static CaptureContext g_captureCtx{};

// Completion callback for async operations
static void CALLPASCAL CompletionProc_Capture(
    LPNkMAIDObject pObject,
    ULONG ulCommand,
    ULONG ulParam,
    ULONG ulDataType,
    NKPARAM data,
    NKREF refComplete,
    NKERROR nResult)
{
    CaptureContext* pCtx = (CaptureContext*)refComplete;

    if (ulCommand == kNkMAIDCommand_CapStart && ulParam == kNkMAIDCapability_Capture) {
        // Capture completed
        pCtx->captureComplete = true;
        pCtx->lastError = nResult;
        printf("[MAID] CompletionProc: Capture complete, result=%d\n", nResult);
    }
    else if (ulCommand == kNkMAIDCommand_CapStart && ulParam == kNkMAIDCapability_Acquire) {
        // Acquire (download) completed
        pCtx->downloadComplete = true;
        pCtx->lastError = nResult;
        printf("[MAID] CompletionProc: Acquire complete, result=%d\n", nResult);
    }
}

// Event callback for detecting new items after capture
static NKERROR CALLPASCAL EventProc_Capture(NKREF refProc, ULONG ulEvent, NKPARAM data)
{
    CaptureContext* pCtx = (CaptureContext*)refProc;

    if (ulEvent == kNkMAIDEvent_AddChild) {
        // New item (image) detected!
        pCtx->newItemID = (SLONG)data;
        printf("[MAID] EventProc: AddChild event, itemID=%d\n", pCtx->newItemID);
    }

    return kNkMAIDResult_NoError;
}

// DataProc callback for receiving image data chunks
static NKERROR CALLPASCAL DataProc_Capture(NKREF ref, LPVOID pInfo, LPVOID pData)
{
    CaptureContext* pCtx = (CaptureContext*)ref;
    LPNkMAIDDataInfo pDataInfo = (LPNkMAIDDataInfo)pInfo;

    if (pDataInfo->ulType & kNkMAIDDataObjType_File) {
        // File data (JPEG/NEF/TIFF)
        LPNkMAIDFileInfo pFileInfo = (LPNkMAIDFileInfo)pInfo;

        // Allocate buffer on first chunk
        if (pCtx->imageBuffer == NULL) {
            pCtx->bufferSize = pFileInfo->ulTotalLength;
            pCtx->imageBuffer = malloc(pCtx->bufferSize);
            pCtx->fileDataType = pFileInfo->ulFileDataType;
            printf("[MAID] DataProc: Allocating %u bytes for image\n", pCtx->bufferSize);

            if (pCtx->imageBuffer == NULL) {
                printf("[MAID] DataProc: Out of memory!\n");
                return kNkMAIDResult_OutOfMemory;
            }
        }

        // Copy this chunk
        ULONG offset = pFileInfo->ulTotalLength - pFileInfo->ulLength;
        memcpy((char*)pCtx->imageBuffer + offset, pData, pFileInfo->ulLength);

        printf("[MAID] DataProc: Received chunk at offset %u, size %u (total %u)\n",
               offset, pFileInfo->ulLength, pFileInfo->ulTotalLength);

        // Check if transfer complete
        if (offset + pFileInfo->ulLength >= pFileInfo->ulTotalLength) {
            printf("[MAID] DataProc: Transfer complete, saving file...\n");

            // Determine file extension
            const char* ext = ".dat";
            switch(pCtx->fileDataType) {
                case kNkMAIDFileDataType_JPEG: ext = ".jpg"; break;
                case kNkMAIDFileDataType_TIFF: ext = ".tif"; break;
                case kNkMAIDFileDataType_NIF:  ext = ".nef"; break;
            }

            // Generate unique filename
            char filename[256];
            int i = 0;
            FILE* testFile = NULL;
            do {
                sprintf_s(filename, sizeof(filename), "capture_%03d%s", ++i, ext);
                sprintf_s(pCtx->savedFilePath, sizeof(pCtx->savedFilePath), "%s\\%s",
                         pCtx->watchDirPath, filename);
                fopen_s(&testFile, pCtx->savedFilePath, "r");
                if (testFile) fclose(testFile);
            } while (testFile != NULL && i < 999);

            // Write file
            FILE* outFile = NULL;
            fopen_s(&outFile, pCtx->savedFilePath, "wb");
            if (outFile) {
                fwrite(pCtx->imageBuffer, 1, pCtx->bufferSize, outFile);
                fclose(outFile);
                printf("[MAID] DataProc: Saved to %s\n", pCtx->savedFilePath);
            } else {
                printf("[MAID] DataProc: Failed to open file for writing!\n");
                return kNkMAIDResult_UnexpectedError;
            }

            // Free buffer
            free(pCtx->imageBuffer);
            pCtx->imageBuffer = NULL;
        }
    }

    return kNkMAIDResult_NoError;
}

array<System::String^>^ MaidBridge::Shoot(System::String^ watchDir)
{
    Console::WriteLine("[MAID] Shoot() called - triggering shutter and downloading from SD card");

    if (!connected || pSourceObj == IntPtr::Zero) {
        Console::WriteLine("[MAID] Shoot: Not connected or no source");
        return gcnew array<System::String^>(0);
    }

    NkMAIDObject* pSrc = static_cast<NkMAIDObject*>(pSourceObj.ToPointer());

    // Initialize capture context
    memset(&g_captureCtx, 0, sizeof(g_captureCtx));

    // Convert watchDir to native string
    std::string watchDirNative = msclr::interop::marshal_as<std::string>(watchDir);
    strncpy_s(g_captureCtx.watchDirPath, sizeof(g_captureCtx.watchDirPath),
              watchDirNative.c_str(), _TRUNCATE);

    Console::WriteLine("[MAID] Shoot: Triggering shutter (CapStart on Capture)...");

    // Trigger capture
    SLONG result = CallMAID(pSrc, kNkMAIDCommand_CapStart, kNkMAIDCapability_Capture,
                      kNkMAIDDataType_Null, NULL);

    if (result != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] Shoot: CapStart failed with error {0}", result));
        throw gcnew Exception("Failed to trigger capture. Error code: " + result.ToString());
    }

    Console::WriteLine("[MAID] Shoot: Waiting for camera to finish capture...");

    // Wait and retry enumeration a few times
    int retries = 5;
    bool enumSuccess = false;

    for (int i = 0; i < retries && !enumSuccess; i++) {
        System::Threading::Thread::Sleep(1000);  // Wait 1 second between tries

        Console::WriteLine(String::Format("[MAID] Shoot: Enumerating items (attempt {0}/{1})...", i + 1, retries));
        result = CallMAID(pSrc, kNkMAIDCommand_EnumChildren, 0, kNkMAIDDataType_Null, NULL);

        if (result == kNkMAIDResult_NoError) {
            enumSuccess = true;
        } else {
            Console::WriteLine(String::Format("[MAID] EnumChildren returned error {0}, retrying...", result));
        }
    }

    if (!enumSuccess) {
        Console::WriteLine("[MAID] Failed to enumerate children after multiple attempts");
        return gcnew array<System::String^>(0);
    }

    // Get list of items
    NkMAIDEnum stItemEnum;
    memset(&stItemEnum, 0, sizeof(stItemEnum));
    result = CallMAID(pSrc, kNkMAIDCommand_CapGet, kNkMAIDCapability_Children,
                      kNkMAIDDataType_EnumPtr, &stItemEnum);

    if (result != kNkMAIDResult_NoError || stItemEnum.ulElements == 0) {
        Console::WriteLine("[MAID] No items found on SD card");
        return gcnew array<System::String^>(0);
    }

    Console::WriteLine(String::Format("[MAID] Found {0} items on SD card", stItemEnum.ulElements));

    // Allocate buffer for item IDs
    ULONG* pItemIDs = new ULONG[stItemEnum.ulElements];
    stItemEnum.pData = pItemIDs;

    result = CallMAID(pSrc, kNkMAIDCommand_CapGetArray, kNkMAIDCapability_Children,
                      kNkMAIDDataType_EnumPtr, &stItemEnum);

    if (result != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] CapGetArray failed (error {0})", result));
        delete[] pItemIDs;
        return gcnew array<System::String^>(0);
    }

    // Use the last item (most recent)
    ULONG latestItemID = pItemIDs[stItemEnum.ulElements - 1];
    delete[] pItemIDs;

    Console::WriteLine(String::Format("[MAID] Latest item ID: {0}", latestItemID));

    // Open the latest Item
    Console::WriteLine("[MAID] Shoot: Opening item object...");
    NkMAIDObject itemObj{};
    itemObj.refClient = (NKREF)&g_captureCtx;

    result = CallMAID(pSrc, kNkMAIDCommand_Open, latestItemID,
                      kNkMAIDDataType_ObjectPtr, &itemObj);

    if (result != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] Shoot: Failed to open item (error {0})", result));
        return gcnew array<System::String^>(0);
    }

    Console::WriteLine("[MAID] Shoot: Enumerating item children (data objects)...");
    result = CallMAID(&itemObj, kNkMAIDCommand_EnumChildren, 0, kNkMAIDDataType_Null, NULL);

    // Call Async to let enumeration complete
    for (int i = 0; i < 10; i++) {
        CallMAID(&itemObj, kNkMAIDCommand_Async, 0, kNkMAIDDataType_Null, NULL);
        System::Threading::Thread::Sleep(50);
    }

    // Open the Image data object
    Console::WriteLine("[MAID] Shoot: Opening image data object...");
    NkMAIDObject imageObj{};
    imageObj.refClient = (NKREF)&g_captureCtx;

    result = CallMAID(&itemObj, kNkMAIDCommand_Open, kNkMAIDDataObjType_Image,
                      kNkMAIDDataType_ObjectPtr, &imageObj);

    if (result != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] Shoot: Failed to open image object (error {0})", result));
        result = g_pMAIDEntryPoint(pSrc, kNkMAIDCommand_Close, itemObj.ulID, kNkMAIDDataType_Null, NULL, NULL, NULL);
        return gcnew array<System::String^>(0);
    }

    // Set DataProc callback
    Console::WriteLine("[MAID] Shoot: Setting DataProc callback...");
    NkMAIDCallback dataProc;
    dataProc.pProc = (LPNKFUNC)DataProc_Capture;
    dataProc.refProc = (NKREF)&g_captureCtx;

    result = CallMAID(&imageObj, kNkMAIDCommand_CapSet, kNkMAIDCapability_DataProc,
                      kNkMAIDDataType_CallbackPtr, &dataProc);

    if (result != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] Warning: Failed to set DataProc (error {0})", result));
    }

    // Start acquiring (downloading) image
    Console::WriteLine("[MAID] Shoot: Starting image acquisition from SDRAM...");
    g_captureCtx.downloadComplete = false;

    result = CallMAID(&imageObj, kNkMAIDCommand_CapStart, kNkMAIDCapability_Acquire,
                      kNkMAIDDataType_Null, NULL);

    if (result != kNkMAIDResult_NoError) {
        Console::WriteLine(String::Format("[MAID] Shoot: Acquire failed (error {0})", result));
        g_pMAIDEntryPoint(&itemObj, kNkMAIDCommand_Close, imageObj.ulID, kNkMAIDDataType_Null, NULL, NULL, NULL);
        g_pMAIDEntryPoint(pSrc, kNkMAIDCommand_Close, itemObj.ulID, kNkMAIDDataType_Null, NULL, NULL, NULL);
        return gcnew array<System::String^>(0);
    }

    // Wait for download to complete
    Console::WriteLine("[MAID] Shoot: Waiting for download...");
    int waited = 0;
    int maxWait = 200; // 20 seconds
    while (!g_captureCtx.downloadComplete && waited < maxWait) {
        CallMAID(&imageObj, kNkMAIDCommand_Async, 0, kNkMAIDDataType_Null, NULL);
        System::Threading::Thread::Sleep(100);
        waited++;
    }

    // Reset DataProc
    CallMAID(&imageObj, kNkMAIDCommand_CapSet, kNkMAIDCapability_DataProc,
             kNkMAIDDataType_Null, NULL);

    // Close objects
    Console::WriteLine("[MAID] Shoot: Closing objects...");
    g_pMAIDEntryPoint(&itemObj, kNkMAIDCommand_Close, imageObj.ulID, kNkMAIDDataType_Null, NULL, NULL, NULL);
    g_pMAIDEntryPoint(pSrc, kNkMAIDCommand_Close, itemObj.ulID, kNkMAIDDataType_Null, NULL, NULL, NULL);

    // Return result
    if (g_captureCtx.savedFilePath[0] != '\0') {
        Console::WriteLine(String::Format("[MAID] Shoot: Success! File saved: {0}",
                          gcnew String(g_captureCtx.savedFilePath)));
        array<System::String^>^ files = gcnew array<System::String^>(1);
        files[0] = gcnew String(g_captureCtx.savedFilePath);
        return files;
    } else {
        Console::WriteLine("[MAID] Shoot: No file was saved");
        return gcnew array<System::String^>(0);
    }
}

System::String^ MaidBridge::TestLiveViewMode()
{
    Console::WriteLine("[MAID] ========== TestLiveViewMode() STANDALONE TEST ==========");

    if (!connected || pSourceObj == IntPtr::Zero || g_pMAIDEntryPoint == nullptr) {
        return "ERROR: Not connected or no entry point";
    }

    NkMAIDObject* pSource = static_cast<NkMAIDObject*>(pSourceObj.ToPointer());
    System::Text::StringBuilder^ sb = gcnew System::Text::StringBuilder();
    SLONG result;

    sb->AppendLine("=== STEP 1: Set LiveViewStatus to OFF (0) ===");
    result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapSet, kNkMAIDCapability_LiveViewStatus,
                                kNkMAIDDataType_Unsigned, (NKPARAM)0, NULL, NULL);
    sb->AppendLine(String::Format("CapSet(0): result={0}", result));
    Sleep(200);

    sb->AppendLine("\n=== STEP 2: Set LiveViewStatus to RemoteLV (3) ===");
    result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapSet, kNkMAIDCapability_LiveViewStatus,
                                kNkMAIDDataType_Unsigned, (NKPARAM)3, NULL, NULL);
    sb->AppendLine(String::Format("CapSet(3): result={0}", result));

    sb->AppendLine("\n=== STEP 3: Wait 1 second for camera ===");
    Sleep(1000);

    sb->AppendLine("\n=== STEP 4: Pump Async 20 times ===");
    for (int i = 0; i < 20; i++) {
        result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_Async, 0, kNkMAIDDataType_Null, NULL, NULL, NULL);
        Sleep(50);
    }
    sb->AppendLine("Done pumping async");

    sb->AppendLine("\n=== STEP 5: Check LiveViewImageStatus (0x8517) using EnumPtr ===");
    {
        // LiveViewImageStatus is an enum type - must use NkMAIDEnum structure
        // kNkMAIDLiveViewImageStatus: 0=CannotAcquire, 1=CanAcquire
        NkMAIDEnum stEnum;
        memset(&stEnum, 0, sizeof(NkMAIDEnum));

        result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGet, 0x8517,  // LiveViewImageStatus
                                    kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum,
                                    NULL, NULL);
        sb->AppendLine(String::Format("LiveViewImageStatus: result={0}, ulValue={1}, ulElements={2}, ulType={3}",
            result, stEnum.ulValue, stEnum.ulElements, stEnum.ulType));
        sb->AppendLine("  (ulValue: 0=CannotAcquire, 1=CanAcquire)");
    }

    sb->AppendLine("\n=== STEP 6: Wait for LiveViewImageStatus event and check ===");
    {
        g_liveViewStatusChanged = false;

        for (int attempt = 0; attempt < 5; attempt++) {
            // Pump async and wait for status change event
            for (int i = 0; i < 50; i++) {
                g_pMAIDEntryPoint(pSource, kNkMAIDCommand_Async, 0, kNkMAIDDataType_Null, NULL, NULL, NULL);
                Sleep(20);
                if (g_liveViewStatusChanged) break;
            }

            // Check status using correct enum data type
            NkMAIDEnum stEnum;
            memset(&stEnum, 0, sizeof(NkMAIDEnum));
            result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGet, 0x8517,
                                        kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum,
                                        NULL, NULL);

            sb->AppendLine(String::Format("Attempt {0}: eventFired={1}, result={2}, status={3}",
                attempt + 1, g_liveViewStatusChanged, result, stEnum.ulValue));

            // If status is CanAcquire (1), try to read frame using proper async pattern
            if (stEnum.ulValue == 1) {
                sb->AppendLine("  Status=CanAcquire, attempting to read frame with completion callback...");

                // Phase 1: Get array metadata with completion callback
                NkMAIDArray stArray;
                memset(&stArray, 0, sizeof(NkMAIDArray));

                volatile ULONG ulCount1 = 0;
                RefCompletionProc refProc1;
                refProc1.pulCount = &ulCount1;
                refProc1.pRef = NULL;
                refProc1.nResult = 0;

                SLONG phase1Result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGet, 0x8247,
                                            kNkMAIDDataType_ArrayPtr, (NKPARAM)&stArray,
                                            (LPNKFUNC)CompletionProc_Generic, (NKREF)&refProc1);

                // Wait for completion
                IdleLoop(pSource, &ulCount1, 1, 500);

                sb->AppendLine(String::Format("  Phase1 (CapGet metadata): result={0}, callback={1}, elements={2}, physBytes={3}",
                    phase1Result, ulCount1, stArray.ulElements, stArray.wPhysicalBytes));

                if (phase1Result == 0 && stArray.ulElements > 0) {
                    // Phase 2: Allocate buffer and try CapGetArray
                    ULONG bufSize = stArray.ulElements * (stArray.wPhysicalBytes > 0 ? stArray.wPhysicalBytes : 1);
                    stArray.pData = malloc(bufSize);
                    memset(stArray.pData, 0xDD, bufSize);

                    volatile ULONG ulCount2 = 0;
                    RefCompletionProc refProc2;
                    refProc2.pulCount = &ulCount2;
                    refProc2.pRef = NULL;
                    refProc2.nResult = 0;

                    SLONG phase2Result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGetArray, 0x8247,
                                                kNkMAIDDataType_ArrayPtr, (NKPARAM)&stArray,
                                                (LPNKFUNC)CompletionProc_Generic, (NKREF)&refProc2);

                    // Wait for completion
                    IdleLoop(pSource, &ulCount2, 1, 500);

                    unsigned char* pData = (unsigned char*)stArray.pData;
                    int modified = 0;
                    for (ULONG i = 0; i < 100 && i < bufSize; i++) {
                        if (pData[i] != 0xDD) modified++;
                    }

                    sb->AppendLine(String::Format("  Phase2 (CapGetArray): result={0}, callback={1}, callbackResult={2}",
                        phase2Result, ulCount2, refProc2.nResult));
                    sb->AppendLine(String::Format("  Modified bytes in first 100: {0}", modified));
                    sb->AppendLine(String::Format("  First 8: {0:X2} {1:X2} {2:X2} {3:X2} {4:X2} {5:X2} {6:X2} {7:X2}",
                        pData[0], pData[1], pData[2], pData[3], pData[4], pData[5], pData[6], pData[7]));
                    sb->AppendLine(String::Format("  @512: {0:X2} {1:X2} {2:X2} {3:X2}",
                        pData[512], pData[513], pData[514], pData[515]));

                    // If CapGetArray failed, try just CapGet with pre-allocated buffer + completion
                    if (phase2Result != 0 || modified == 0) {
                        sb->AppendLine("  CapGetArray failed or no data, trying CapGet with buffer...");
                        memset(stArray.pData, 0xEE, bufSize);

                        volatile ULONG ulCount3 = 0;
                        RefCompletionProc refProc3;
                        refProc3.pulCount = &ulCount3;
                        refProc3.pRef = NULL;
                        refProc3.nResult = 0;

                        SLONG phase3Result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGet, 0x8247,
                                                    kNkMAIDDataType_ArrayPtr, (NKPARAM)&stArray,
                                                    (LPNKFUNC)CompletionProc_Generic, (NKREF)&refProc3);

                        IdleLoop(pSource, &ulCount3, 1, 500);

                        modified = 0;
                        for (ULONG i = 0; i < 100 && i < bufSize; i++) {
                            if (pData[i] != 0xEE) modified++;
                        }

                        sb->AppendLine(String::Format("  Phase3 (CapGet with buffer): result={0}, callback={1}, modified={2}",
                            phase3Result, ulCount3, modified));
                        sb->AppendLine(String::Format("  First 8: {0:X2} {1:X2} {2:X2} {3:X2} {4:X2} {5:X2} {6:X2} {7:X2}",
                            pData[0], pData[1], pData[2], pData[3], pData[4], pData[5], pData[6], pData[7]));
                    }

                    free(stArray.pData);
                }
            }

            g_liveViewStatusChanged = false;
        }
    }

    sb->AppendLine("\n=== STEP 7: Done with tests ===");

    sb->AppendLine("\n=== STEP 8: Set LiveViewStatus back to OFF ===");
    result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapSet, kNkMAIDCapability_LiveViewStatus,
                                kNkMAIDDataType_Unsigned, (NKPARAM)0, NULL, NULL);
    sb->AppendLine(String::Format("CapSet(0): result={0}", result));

    Console::WriteLine("[MAID] ========== TestLiveViewMode() COMPLETE ==========");
    return sb->ToString();
}

