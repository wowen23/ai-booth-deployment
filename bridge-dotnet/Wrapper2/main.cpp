#include <windows.h>
#include <cstdio>

int main() {
    HMODULE h = LoadLibraryW(L"Type0029.md3");
    if (!h) {
        wprintf(L"Failed to load Type0029.md3\n");
        return 1;
    }
    FARPROC p = GetProcAddress(h, "MAIDEntryPoint");
    if (!p) {
        wprintf(L"MAIDEntryPoint not found in Type0029.md3\n");
        FreeLibrary(h);
        return 2;
    }
    wprintf(L"MAID module loaded and entry point resolved.\n");
    FreeLibrary(h);
    return 0;
}