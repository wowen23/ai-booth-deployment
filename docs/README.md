# Documentation Index

Quick navigation to all project documentation.

## 🚀 Start Here

**New to this project? Read this first:**
- **[START_HERE.md](START_HERE.md)** - Complete quick start guide with setup instructions, troubleshooting, and workflow explanations

## 📚 Core Documentation

### For Developers
- **[CLAUDE.md](../CLAUDE.md)** - Comprehensive developer guide (in repo root)
  - Build commands for .NET and Python
  - Architecture overview
  - File responsibilities
  - Development workflow
  - Troubleshooting build errors
  - Deployment checklist

### Original Handoff
- **[INSTRUCTIONS.md](INSTRUCTIONS.md)** - Original project handoff document
  - What was working at handoff
  - Visual Studio setup instructions
  - Initial SDK integration steps

## 🏗️ Architecture & Planning

### System Design
- **[SDK_BRIDGE_PLAN.md](SDK_BRIDGE_PLAN.md)** - Camera bridge architecture
  - Why we need a .NET bridge
  - HTTP endpoints design
  - Configuration approach
  - Milestones and goals

- **[PHASE4_WEB_PLAN.md](PHASE4_WEB_PLAN.md)** - Web application design
  - iPad-friendly UI requirements
  - API endpoint contracts
  - Security considerations
  - Hosting options

### Implementation Progress
- **[SDK_IMPLEMENTATION_PROGRESS.md](SDK_IMPLEMENTATION_PROGRESS.md)** - Camera SDK integration progress
  - Major achievements (camera connection working!)
  - Technical insights and breakthroughs
  - Current status of live view
  - Next steps for completion

## 📖 Reference Material

### Nikon SDK API Documentation
These are auto-extracted from Nikon's PDF documentation for easy searching:

- **[MAID3.txt](MAID3.txt)** - Core MAID3 API reference (181 KB)
  - Basic SDK concepts
  - Module/Source/Item hierarchy
  - Capability system
  - Error codes

- **[MAID3Type0029.txt](MAID3Type0029.txt)** - Type0029 module specifics (509 KB)
  - USB PTP protocol implementation
  - Z6 II specific capabilities
  - Live view implementation
  - Capture and download flows

- **[Z6_2UsbMtp.txt](Z6_2UsbMtp.txt)** - Z6 II USB/MTP reference (639 KB)
  - Camera-specific USB behavior
  - MTP protocol details
  - Device enumeration

## 🗄️ Archived Documentation

- **[archive/](archive/)** - Obsolete documentation
  - MTP approach documentation (abandoned)
  - See `archive/README.md` for details on why these are archived

## Documentation Tree

```
docs/
├── README.md                          (this file)
├── START_HERE.md                      👈 READ THIS FIRST
├── INSTRUCTIONS.md                    (original handoff)
│
├── SDK_BRIDGE_PLAN.md                 (architecture)
├── PHASE4_WEB_PLAN.md                 (web app design)
├── SDK_IMPLEMENTATION_PROGRESS.md     (technical progress)
│
├── MAID3.txt                          (SDK reference)
├── MAID3Type0029.txt                  (SDK reference)
├── Z6_2UsbMtp.txt                     (SDK reference)
│
└── archive/                           (old/abandoned docs)
    ├── README.md                      (why archived)
    ├── MTP_BRIDGE_README.md
    ├── MTP_INTEGRATION_SUMMARY.md
    ├── MTP_PYTHON_COMPLETE.md
    ├── PYTHON_MTP_SETUP.md
    └── RECOMMENDATION.md
```

## Quick Links by Task

### "I want to run the application"
→ [START_HERE.md](START_HERE.md)

### "I want to understand the architecture"
→ [CLAUDE.md](../CLAUDE.md) → [SDK_BRIDGE_PLAN.md](SDK_BRIDGE_PLAN.md) → [PHASE4_WEB_PLAN.md](PHASE4_WEB_PLAN.md)

### "I want to build the .NET bridge"
→ [CLAUDE.md](../CLAUDE.md) (Build Commands section)

### "I want to understand the camera SDK"
→ [SDK_IMPLEMENTATION_PROGRESS.md](SDK_IMPLEMENTATION_PROGRESS.md) → [MAID3Type0029.txt](MAID3Type0029.txt)

### "I'm getting errors"
→ [START_HERE.md](START_HERE.md) (Troubleshooting section) → [CLAUDE.md](../CLAUDE.md) (Troubleshooting section)

### "What happened to the MTP approach?"
→ [archive/README.md](archive/README.md)

---

**Last Updated:** January 6, 2026
**Maintained by:** See git log for contributors
