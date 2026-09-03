# iPhone DCIM Backup Tool

A Python script designed to backup iPhone photos and videos over USB (AFC protocol) using `pymobiledevice3` and `t3` (tidevice3). It automatically detects missing local albums and decides whether to perform a fast whole-folder download or a per-file sync.

## Prerequisites

- **Python**: 3.8 or higher
- **System Tools**: 
  - `pymobiledevice3` (for fast whole-folder pulling)
  - `t3` / `tidevice3` (for directory listing fallback and per-file syncing)

Ensure your iOS device is unlocked and you have trusted the connected computer before running the script.

## Installation

1. Clone or download this repository.
2. Install required Python packages:

```bash
pip install -r requirements.txt
