# iPhone DCIM Backup Tool

A Python script designed to back up iPhone photos and videos over USB (AFC protocol) using `pymobiledevice3` and `t3` (`tidevice3`). It automatically detects missing local albums and intelligently switches between fast whole-folder downloads and per-file synchronization.

## Prerequisites

- **Python**: 3.8 or higher
- **System Tools**: 
- `pymobiledevice3` (for fast whole-folder pulling)
- `t3` / `tidevice3` (for directory listing fallback and per-file syncing)

Ensure your iOS device is unlocked and you have clicked **"Trust This Computer"** on your device before running the script.

## Installation

1. Clone or download this repository.
2. Install the required Python dependencies:

```bash
pip install -r requirements.txt

```


## Usage & Workflows


Run the script from your target local backup directory (e.g., inside your external hard drive directory such as `DCIM_iPhone14ProMax`).
### 1. Incremental Backup (Default Mode)


Scans all remote DCIM albums and automatically downloads albums that do not exist locally or have missing files:
```bash
python pull_images_v5.py --new

```


### 2. Prioritize Newer Albums


Processes albums in reverse numerical order so that newly created photo albums (higher numbers) are downloaded first:
```bash
python pull_images_v5.py --new --newest-first

```


### 3. Backup a Specific Album / Resume Interrupted Download


Target or resume a single album by name (e.g., `702APPLE`):
```bash
python pull_images_v5.py --folder "702APPLE"

```


### 4. Full Synchronization (All Remote Albums)


Scans every album on the device and downloads any missing photos across all folders:
```bash
python pull_images_v5.py --all

```


### 5. Force Whole-Folder Pull


Forces `pymobiledevice3` whole-folder download even if only a few files are missing:
```bash
python pull_images_v5.py --folder "702APPLE" --force-folder

```


### 6. Legacy Mode (Per-File Sync)


Falls back to multi-threaded per-file sync using `t3`:
```bash
python pull_images_v5.py --legacy --folders all --files all

```


## Command-Line Options


| Flag | Description | Default |
| --- | --- | --- |
| `--new` | Process only albums missing locally or incomplete | `True` |
| `--all` | Scan all remote albums and pull missing files | `False` |
| `--folder <NAME` | Target a specific folder (e.g., `702APPLE`) | None |
| `--newest-first` | Sort albums in descending order (newer albums first) | `False` |
| `--missing-count <INT` | Missing file count threshold to trigger whole-folder pull | `50` |
| `--missing-pct <FLOAT` | Missing file percentage threshold to trigger whole-folder pull | `10.0` |
| `--force-folder` | Force whole-folder pull for the target album | `False` |
| `--legacy` | Switch to legacy `t3` per-file sync mode | `False` |
| `-debug 1` | Output detailed file list debugging information | `0` |


## Troubleshooting


* **Script Hanging / Freeze**:
The script includes a 20-second timeout mechanism. If `pymobiledevice3` times out, it automatically falls back to `t3`. If it stays unresponsive, unlock your iPhone screen and re-plug the USB cable.
* **Pairing & Trust Issues**:
If remote folders cannot be listed, run `pymobiledevice3 lockdownd pair` in your terminal to re-pair and trust your computer.
* **Interrupting & Resuming**:
You can safely interrupt the process anytime using `Ctrl + C`. Rerunning the command will skip already completed files.


## License & Disclaimer


Distributed under the MIT License. This tool is provided "AS IS", without warranty of any kind. Always verify your backups before deleting original media from your device.
```
