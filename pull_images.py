#!/usr/bin/env python3
"""
Pull iPhone DCIM folders over USB (AFC).

New default path uses pymobiledevice3 whole-folder pull for missing
(or mostly-missing) albums. The old per-file t3 path is kept behind --legacy.

Examples (run from the local DCIM dest, e.g. DCIM_iPhone14ProMax):

  # only albums that do not exist locally
  python pull_images_v5.py --new

  # every remote album; skip ones that already look complete
  python pull_images_v5.py --all

  # one album (interrupted 702APPLE, or any name)
  python pull_images_v5.py --folder 702APPLE

  # old script behaviour: t3 per-file, first N folders / first M new files
  python pull_images_v5.py --legacy --folders all --files all
  python pull_images_v5.py --legacy --folders 2 --files 5
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing
import os
import platform
import re
import subprocess
import sys
import time
import warnings
from datetime import datetime

from colorama import Fore, Style

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
warnings.filterwarnings("ignore")

T3_DIR_RE = re.compile(r"IFDIR\s+\S+\s+([\w.]+)/?")
T3_FILE_RE = re.compile(r"IFREG\s+\S+\s+([\w.]+)")


def run_command(cmd: str, timeout: int | None = 30) -> str:
    """Run shell command with clear stdout logging and timeout protection."""
    print(f"{Fore.BLUE}[CMD]{Style.RESET_ALL} {cmd}", flush=True)
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0 and result.stderr:
            logging.warning(f"Command returned exit code {result.returncode}: {result.stderr.strip()}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"{Fore.RED}[TIMEOUT]{Style.RESET_ALL} Command timed out after {timeout}s: {cmd}", flush=True)
        return ""


def run_command_checked(cmd: list[str] | str) -> subprocess.CompletedProcess:
    if isinstance(cmd, str):
        print(f"{Fore.BLUE}[CMD]{Style.RESET_ALL} {cmd}", flush=True)
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"{Fore.BLUE}[CMD]{Style.RESET_ALL} {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, capture_output=True, text=True)


def cpu_workers() -> int:
    if platform.system() == "Darwin":
        cores = int(run_command("sysctl -n hw.ncpu", timeout=5) or "4")
    else:
        cores = int(run_command("nproc", timeout=5) or "4")
    return max(1, int(cores * 3 / 4 - 1))


def parse_names(ls_text: str, t3_pattern: re.Pattern[str]) -> list[str]:
    names = t3_pattern.findall(ls_text)
    if names:
        return names
    out = []
    for line in ls_text.splitlines():
        line = line.strip().rstrip("/")
        if not line or line in {".", ".."}:
            continue
        if line.startswith("IFDIR") or line.startswith("IFREG"):
            continue
        base = os.path.basename(line)
        if base and base not in out:
            out.append(base)
    return out


def list_remote_folders() -> list[str]:
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Querying remote DCIM directory listing via pymobiledevice3...", flush=True)
    pmd = run_command("pymobiledevice3 afc ls /DCIM", timeout=20)
    folders = parse_names(pmd, T3_DIR_RE)
    if folders:
        return folders
    
    print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} pymobiledevice3 failed or returned empty. Falling back to t3...", flush=True)
    t3 = run_command("t3 fsync ls DCIM", timeout=20)
    return parse_names(t3, T3_DIR_RE)


def list_remote_files(folder: str) -> list[str]:
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Querying file list for /DCIM/{folder} via pymobiledevice3...", flush=True)
    pmd = run_command(f'pymobiledevice3 afc ls "/DCIM/{folder}"', timeout=20)
    files = parse_names(pmd, T3_FILE_RE)
    if files:
        return files
    
    print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} pymobiledevice3 returned empty for {folder}. Falling back to t3...", flush=True)
    t3 = run_command(f't3 fsync ls "DCIM/{folder}"', timeout=20)
    return parse_names(t3, T3_FILE_RE)


def local_files(folder: str) -> set[str]:
    if not os.path.isdir(folder):
        return set()
    names = set()
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        if os.path.getsize(path) <= 0:
            continue
        names.add(name)
    return names


def folder_sort_key(name: str) -> tuple:
    m = re.match(r"(\d+)([A-Z]+)$", name, re.I)
    if m:
        return (m.group(2).upper(), -int(m.group(1)))
    return (name, 0)


def print_duration(start_time: float, start_fmt: str) -> None:
    end_time = time.time()
    end_fmt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration = int(end_time - start_time)
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    print("Download complete!", flush=True)
    print(f"Started at: {start_fmt}", flush=True)
    print(f"Finished at: {end_fmt}", flush=True)
    print(f"Total time: {hours:02d}:{minutes:02d}:{seconds:02d} (HH:MM:SS)", flush=True)


def pull_folder_pmd3(folder: str) -> int:
    """Whole-folder pull into cwd. Do not mkdir first."""
    cmd = [
        "pymobiledevice3",
        "afc",
        "pull",
        f"/DCIM/{folder}",
        ".",
        "--ignore-errors",
    ]
    print(f"{Fore.CYAN}Whole-folder pull:{Style.RESET_ALL} {' '.join(cmd)}", flush=True)
    started = time.time()
    proc = subprocess.run(cmd)
    elapsed = int(time.time() - started)
    print(f"Finished {folder} in {elapsed}s, exit={proc.returncode}", flush=True)
    return proc.returncode


def pull_files_t3(folder: str, files: list[str], workers: int, debug: bool) -> None:
    if not files:
        print(f"{Fore.YELLOW}No new files need to be downloaded{Style.RESET_ALL}", flush=True)
        logging.info("No new files need to be downloaded")
        return
    os.makedirs(folder, exist_ok=True)
    print(f"Per-file t3 pull: {len(files)} files, workers={workers}", flush=True)
    if debug:
        print(files, flush=True)
    here = os.getcwd()
    os.chdir(folder)
    try:
        commands = [f't3 fsync pull --force "DCIM/{folder}/{name}"' for name in files]
        with multiprocessing.Pool(processes=max(1, workers)) as pool:
            pool.map(run_command, commands)
    finally:
        os.chdir(here)


def decide_action(
    folder: str,
    remote: list[str],
    local: set[str],
    missing_count: int,
    missing_pct: float,
) -> str:
    """
    skip | folder | files
    """
    if not remote:
        return "skip"
    if not os.path.isdir(folder) or len(local) == 0:
        return "folder"
    missing = [name for name in remote if name not in local]
    if not missing:
        return "skip"
    pct = 100.0 * len(missing) / max(len(remote), 1)
    if len(missing) >= missing_count or pct >= missing_pct:
        return "folder"
    return "files"


def run_smart(args: argparse.Namespace) -> None:
    remote_folders = list_remote_folders()
    if not remote_folders:
        print(f"{Fore.RED}No remote DCIM folders found. Is the phone unlocked and computer trusted?{Style.RESET_ALL}", flush=True)
        sys.exit(1)

    if args.folder:
        wanted = args.folder.strip().rstrip("/")
        if wanted not in remote_folders:
            print(f"{Fore.RED}Remote folder not found: {wanted}{Style.RESET_ALL}", flush=True)
            print("Available (first 20):", remote_folders[:20], flush=True)
            sys.exit(1)
        selected = [wanted]
        label = f"specific folder {wanted}"
    elif args.new:
        selected = [name for name in remote_folders if not os.path.isdir(name) or len(local_files(name)) == 0]
        label = "new local folders only"
    else:
        selected = list(remote_folders)
        label = "all remote folders"

    if args.newest_first:
        selected = sorted(selected, key=folder_sort_key)

    print(f"Remote albums: {len(remote_folders)}", flush=True)
    print(f"Selected ({label}): {len(selected)}", flush=True)
    if args.debug:
        print(selected, flush=True)

    workers = cpu_workers()
    print(f"file-level workers: {workers}", flush=True)

    for idx, folder in enumerate(selected, start=1):
        print("\n", "=" * 30, flush=True)
        print(f"Processing folder [{idx}/{len(selected)}] : {folder}", flush=True)

        remote = list_remote_files(folder)
        local = local_files(folder)
        missing = [name for name in remote if name not in local]
        print(f"Remote files: {len(remote)}", flush=True)
        print(f"Local files:  {len(local)}", flush=True)
        print(f"Missing:      {len(missing)}", flush=True)

        action = decide_action(
            folder,
            remote,
            local,
            missing_count=args.missing_count,
            missing_pct=args.missing_pct,
        )
        if args.force_folder and action != "skip":
            action = "folder"

        if action == "skip":
            print(f"{Fore.YELLOW}Skip (complete or empty remote){Style.RESET_ALL}", flush=True)
            logging.info("Skip %s", folder)
            continue

        if action == "folder":
            logging.info("Whole-folder pull %s (%s missing of %s)", folder, len(missing), len(remote))
            pull_folder_pmd3(folder)
            continue

        logging.info("Per-file pull %s (%s files)", folder, len(missing))
        pull_files_t3(folder, missing, workers=min(workers, 4), debug=args.debug)


def run_legacy(args: argparse.Namespace) -> None:
    workers = cpu_workers()
    print(f"available_cores workers: {workers}", flush=True)

    folders = list_remote_folders()
    if not folders:
        print(f"{Fore.RED}No remote DCIM folders found.{Style.RESET_ALL}", flush=True)
        sys.exit(1)

    if args.folder:
        wanted = args.folder.strip().rstrip("/")
        folders = [wanted] if wanted in folders else []
        if not folders:
            print(f"{Fore.RED}Remote folder not found: {wanted}{Style.RESET_ALL}", flush=True)
            sys.exit(1)
    elif args.folders == "all":
        pass
    else:
        folders = folders[: min(int(args.folders), len(folders))]

    print(f"Legacy t3 per-file. Folders: {len(folders)}", flush=True)
    print(folders, flush=True)

    for idx, folder in enumerate(folders, start=1):
        print("\n", "=" * 30, flush=True)
        print(f"Processing folder [{idx}/{len(folders)}] : {folder}", flush=True)
        os.makedirs(folder, exist_ok=True)
        remote = list_remote_files(folder)
        local = local_files(folder)
        new_files = [name for name in remote if name not in local]
        print(f"Found {len(remote)} files in DCIM/{folder}", flush=True)
        print(f"New files to download: {len(new_files)}", flush=True)

        if args.files == "all":
            files_to_process = new_files
        else:
            files_to_process = new_files[: min(int(args.files), len(new_files))]

        print(f"Files to process [{len(files_to_process)}]", flush=True)
        if args.debug:
            print(files_to_process, flush=True)
        pull_files_t3(folder, files_to_process, workers=workers, debug=args.debug)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull iPhone DCIM albums. Default is smart whole-folder pull for new albums."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--new", action="store_true", help="Only albums missing locally (default)")
    mode.add_argument("--all", action="store_true", help="All remote albums; skip complete ones")
    mode.add_argument("--folder", type=str, help='One album name, e.g. "702APPLE"')
    mode.add_argument("--legacy", action="store_true", help="Old t3 per-file path (--folders / --files)")

    parser.add_argument("--folders", type=str, default="2", help="Legacy: how many folders (or 'all')")
    parser.add_argument("--files", type=str, default="5", help="Legacy: how many new files per folder (or 'all')")
    parser.add_argument(
        "--missing-count",
        type=int,
        default=50,
        help="If missing files >= this, whole-folder pull instead of per-file (default 50)",
    )
    parser.add_argument(
        "--missing-pct",
        type=float,
        default=10.0,
        help="If missing percent >= this, whole-folder pull (default 10)",
    )
    parser.add_argument(
        "--force-folder",
        action="store_true",
        help="Force pymobiledevice3 whole-folder pull even when only a few files are missing",
    )
    parser.add_argument("--newest-first", action="store_true", help="Sort 801APPLE before 126APPLE")
    parser.add_argument("-debug", "--debug", type=int, default=0, help="Print file lists")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.legacy and not args.all and not args.folder and not args.new:
        args.new = True

    start_time = time.time()
    start_fmt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info("Started at: %s", start_fmt)
    print(f"cwd: {os.getcwd()}", flush=True)

    try:
        if args.legacy:
            run_legacy(args)
        else:
            run_smart(args)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted. Re-run the same command; complete albums will be skipped.{Style.RESET_ALL}", flush=True)
        sys.exit(130)

    print_duration(start_time, start_fmt)


if __name__ == "__main__":
    main()
