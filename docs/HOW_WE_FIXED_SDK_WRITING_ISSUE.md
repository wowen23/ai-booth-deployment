# How We Fixed the Nikon MAID SDK Live View Buffer Issue

## The Problem

Live view was working only ~25% of the time, usually only on first bridge restart. The SDK's `GetLiveViewImage` capability would:
- Return success (result=0)
- Report correct metadata (elements=708608, physBytes=1)
- But **never write any actual data** to our buffer

We could verify this by filling our buffer with marker bytes (0xAA, 0xDD, etc.) before the call - after the SDK returned "success", the markers were still there.

## The Investigation

### What We Tried (That Didn't Work)

1. **Different buffer sizes** - No effect
2. **Pre-allocated vs SDK-allocated buffers** - No effect
3. **Different data types** - Got -126 (UnexpectedDataType) errors
4. **Checking LiveViewImageStatus** - Initially got -126 because we used wrong data type (UnsignedPtr instead of EnumPtr)

### Key Discovery #1: LiveViewImageStatus is an Enum

The SDK uses `NkMAIDEnum` structure for LiveViewImageStatus (0x8517), not a simple ULONG:

```cpp
// WRONG - returns -126
ULONG status;
result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGet, 0x8517,
                            kNkMAIDDataType_UnsignedPtr, (NKPARAM)&status, NULL, NULL);

// CORRECT
NkMAIDEnum stEnum;
result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGet, 0x8517,
                            kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL);
// stEnum.ulValue = 0 (CannotAcquire) or 1 (CanAcquire)
```

### Key Discovery #2: The SDK Sample Uses Two Phases

Looking at the SDK sample's `GetArrayCapability()` function:

```cpp
// Phase 1: Get metadata
bRet = Command_CapGet(pRefObj->pObject, ulCapID, kNkMAIDDataType_ArrayPtr,
                      (NKPARAM)pstArray, NULL, NULL);

// Phase 2: Allocate and get actual data
pstArray->pData = malloc(pstArray->ulElements * pstArray->wPhysicalBytes);
bRet = Command_CapGetArray(pRefObj->pObject, ulCapID, kNkMAIDDataType_ArrayPtr,
                           (NKPARAM)pstArray, NULL, NULL);
```

### Key Discovery #3: Completion Callbacks + IdleLoop

The SDK sample's `Command_CapGet` and `Command_CapGetArray` both use:
1. A `RefCompletionProc` structure
2. A `CompletionProc` callback
3. An `IdleLoop` that pumps `kNkMAIDCommand_Async` until the callback fires

**This was the critical insight**: The SDK writes data **asynchronously**. Without waiting for the completion callback, we were reading the buffer before the data arrived.

## The Solution

### Working Pattern

```cpp
// Phase 1: Get array metadata with completion callback
NkMAIDArray stArray;
memset(&stArray, 0, sizeof(NkMAIDArray));

volatile ULONG ulCount1 = 0;
RefCompletionProc refProc1;
refProc1.pulCount = &ulCount1;

SLONG result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGet,
                                  kNkMAIDCapability_GetLiveViewImage,
                                  kNkMAIDDataType_ArrayPtr, (NKPARAM)&stArray,
                                  (LPNKFUNC)CompletionProc_Generic, (NKREF)&refProc1);

// Wait for completion
IdleLoop(pSource, &ulCount1, 1, 500);

// Phase 2: Allocate buffer and get actual data
stArray.pData = malloc(stArray.ulElements * stArray.wPhysicalBytes);

volatile ULONG ulCount2 = 0;
RefCompletionProc refProc2;
refProc2.pulCount = &ulCount2;

result = g_pMAIDEntryPoint(pSource, kNkMAIDCommand_CapGetArray,
                            kNkMAIDCapability_GetLiveViewImage,
                            kNkMAIDDataType_ArrayPtr, (NKPARAM)&stArray,
                            (LPNKFUNC)CompletionProc_Generic, (NKREF)&refProc2);

// Wait for completion - THIS IS WHERE THE DATA ACTUALLY ARRIVES
IdleLoop(pSource, &ulCount2, 1, 500);

// Now stArray.pData contains:
// - Bytes 0-511: Header information
// - Bytes 512+: JPEG data (starts with FF D8 FF)
```

### IdleLoop Implementation

```cpp
static bool IdleLoop(LPNkMAIDObject pObject, volatile ULONG* pulCount,
                     ULONG ulEndCount, int maxIterations = 1000)
{
    int iterations = 0;
    while (*pulCount < ulEndCount && iterations < maxIterations) {
        SLONG result = g_pMAIDEntryPoint(pObject, kNkMAIDCommand_Async, 0,
                                          kNkMAIDDataType_Null, NULL, NULL, NULL);
        if (result != kNkMAIDResult_NoError && result != kNkMAIDResult_Pending) {
            break;
        }
        Sleep(1);
        iterations++;
    }
    return *pulCount >= ulEndCount;
}
```

### CompletionProc Callback

```cpp
static void CALLPASCAL CompletionProc_Generic(
    LPNkMAIDObject pObject, ULONG ulCommand, ULONG ulParam,
    ULONG ulDataType, NKPARAM data, NKREF refComplete, NKERROR nResult)
{
    if (refComplete != NULL) {
        RefCompletionProc* pRef = (RefCompletionProc*)refComplete;
        pRef->nResult = nResult;
        if (pRef->pulCount != NULL) {
            (*pRef->pulCount)++;  // Signal completion
        }
    }
}
```

## Why It Worked Sometimes Before

The intermittent success (~25% of the time) was likely due to:
1. **Race condition timing** - Sometimes the async operation completed before we read the buffer
2. **Camera state** - On first connect, the camera might have had data ready in its buffer
3. **Previous async operations** - Leftover async completions from prior calls

## Test Output Showing Success

```
Phase1 (CapGet metadata): result=0, callback=1, elements=708608, physBytes=1
Phase2 (CapGetArray): result=0, callback=1, callbackResult=0
Modified bytes in first 100: 100
First 8: 00 01 00 00 00 00 00 00
@512: FF D8 FF DB
```

- `callback=1` - Completion callback fired
- `Modified bytes: 100` - All marker bytes were overwritten
- `@512: FF D8 FF DB` - JPEG magic bytes (FF D8 = Start of Image)

## Key Takeaways

1. **Always use completion callbacks** with MAID SDK async operations
2. **Always call IdleLoop** (pumping `kNkMAIDCommand_Async`) to allow operations to complete
3. **Use correct data types** - Enums need `NkMAIDEnum` + `EnumPtr`, not `UnsignedPtr`
4. **Two-phase pattern for arrays**: `CapGet` for metadata, `CapGetArray` for data
5. **Read the SDK sample code** - It shows the correct patterns even if documentation is sparse

## Files Modified

- `bridge-dotnet/NikonMaidWrapper/NikonMaidWrapper.cpp`
  - `GetLiveFrame()` - Updated to use two-phase pattern with callbacks
  - `TestLiveViewMode()` - Standalone test function for debugging
  - Added `CompletionProc_Generic`, `IdleLoop`, `RefCompletionProc`
