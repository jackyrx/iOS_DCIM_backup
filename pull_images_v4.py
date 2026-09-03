#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import multiprocessing
from datetime import datetime
import platform
import re

import argparse
from colorama import Fore, Style

import logging
import warnings

# Configure logging and warnings
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
warnings.filterwarnings('ignore')

def run_command(cmd):
    """Run shell command and return output"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def main():

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Pull images from device")
    parser.add_argument("--files", type=str, default="5", help="Number of files to download (or 'all')")
    parser.add_argument("--folders", type=str, default="2", help="Number of folders to process")

    parser.add_argument("-debug", type=int, default=0, help="Debug flag")

    # Parse arguments
    args = parser.parse_args()
    file_count = args.files
    folder_count = args.folders
    flag_debug = args.debug
    
    # Determine available CPU cores
    if platform.system() == "Darwin":  # macOS
        available_cores = int(run_command("sysctl -n hw.ncpu"))
    else:  # Linux
        available_cores = int(run_command("nproc"))
    
    # Set number of threads
    # num_threads = 10
    num_threads = int(available_cores * 3 / 4 - 1)
    print(f"available_cores: {available_cores}")
    print(f"num_threads: {num_threads}")
    
    # Record start time
    start_time = time.time()
    start_time_formatted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"Started at: {start_time_formatted}\n")

    # Get list of folders in DCIM
    dcim_ls = run_command("t3 fsync ls DCIM")
    # print(dcim_ls)

    # Extract folder names using regex - matches IFDIR followed by size then captures folder name
    folder_pattern = r'IFDIR\s+[\w\.]+\s+([\w]+)/'
    folders = re.findall(folder_pattern, dcim_ls)


    # Determine how many files to download based on parameter
    if folder_count == "all":
        folders_to_download = len(folders)
        print(f"Will download ALL {folders_to_download} new folders")
    else:
        folders_to_download = min(int(folder_count), len(folders))
        print(f"Will download {folders_to_download} of {len(folders)} new folders")


    # Limit to requested number of folders
    folders = folders[:folders_to_download]
    print(folders)

    if False:
        # Filter out folders that already exist locally to avoid redundant processing
        folders = [folder for folder in folders if not os.path.exists(folder)]

    print(f"Folders [{folders_to_download}] to process (excluding existing ones)")
    if flag_debug:
        print(f"{folders}")

    # return
    
    # Loop through each folder
    for idx, folder in enumerate(folders):

        print("\n", "="*30)
        print(f"Processing folder [{idx+1}/{folders_to_download}] : {folder}")

        # print(os.getcwd())
        
        # Create directory if it doesn't exist
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            print(f"Created directory: {folder}")
        else:
            print(f"Directory already exists: {folder}")

        os.chdir(folder)
        print(os.getcwd())

        # Get list of files from remote folder
        files_ls = run_command(f't3 fsync ls "DCIM/{folder}"')
        # print(files_ls)

        # Extract filenames using regex - matches IFREG followed by size then captures filename
        file_pattern = r'IFREG\s+[\w\.]+\s+([\w\.]+)'
        all_remote_files = re.findall(file_pattern, files_ls)
        # print(all_remote_files)
        
        print("--" * 5)
        print(f"Found {len(all_remote_files)} files in DCIM/{folder}")

        # Get list of files that already exist in the local folder
        local_existing_files = os.listdir(os.getcwd())

        # Filter out files that already exist locally to avoid redundant downloads
        new_files = [file for file in all_remote_files if not file in local_existing_files]
        print(f"New files to download: {len(new_files)}")
        
        # Determine how many files to download based on parameter
        if file_count == "all":
            files_to_download = len(new_files)
            print(f"Will download ALL {files_to_download} new files")
        else:
            files_to_download = min(int(file_count), len(new_files))
            print(f"Will download {files_to_download} of {len(new_files)} new files")
        
        # Limit to requested number of files
        files_to_process = new_files[:files_to_download]
        print(f"{'-'*5}Files to process [{len(files_to_process)}]: \n")

        if flag_debug:
            print(f"{files_to_process}")


        if len(files_to_process) == 0:
            print(f"{Fore.YELLOW}No new files need to be downloaded{Style.RESET_ALL}")
            logging.info("No new files need to be downloaded\n\n")
        else:
            logging.info(f"New files need to be downloaded {'-'*10} \n\n")
        
        # continue
        # os.chdir("..")

        with multiprocessing.Pool(processes=num_threads) as pool:
            commands = [f't3 fsync pull "DCIM/{folder}/{file}"' for file in files_to_process]
            pool.map(run_command, commands)
        
        # Return to parent directory
        os.chdir("..")
    
    # Record end time and calculate duration
    end_time = time.time()
    end_time_formatted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration = int(end_time - start_time)
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    print("Download complete!")
    print(f"Started at: {start_time_formatted}")
    print(f"Finished at: {end_time_formatted}")
    print(f"Total time: {duration_formatted} (HH:MM:SS)")

if __name__ == "__main__":
    main()







