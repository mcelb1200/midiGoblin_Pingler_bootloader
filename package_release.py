#!/usr/bin/env python3
"""
MIDI Goblin Dual-Bootloader Release Packager
============================================
Packages the consolidated image, individual partition binaries, flashing
scripts, tool installers, and documentation into a redistributable ZIP package.
"""

import os
import sys
import shutil
import zipfile
import hashlib
from pathlib import Path

VERSION = "v1.0.0"
BASE_DIR = Path(__file__).resolve().parent
PKG_NAME = f"midi-goblin-dual-boot-{VERSION}"
PKG_DIR = BASE_DIR / PKG_NAME
ZIP_FILE = BASE_DIR / f"{PKG_NAME}.zip"

ROOT_FILES = [
    "midigoblin_dual_consolidated.bin",
    "flash.bat",
    "flash.sh",
    "flash.py",
    "install_tools.bat",
    "install_tools.sh",
    "verify_image.py",
    "README.md",
    "QUICKSTART.txt",
]

FW_FILES = [
    ("dual_bootloader.bin", BASE_DIR / "dual_bootloader.bin"),
    ("partitions.bin", BASE_DIR / "firmware" / "partitions.bin"),
    ("boot_app0.bin", BASE_DIR / "firmware" / "boot_app0.bin"),
    ("midi_goblin1_0_5.ino.bin", BASE_DIR / "midi_goblin1_0_5.ino.bin"),
    ("MIDI_Goblin_Pingler_v_1_1.bin", BASE_DIR / "MIDI_Goblin_Pingler_v_1_1.bin"),
]

def make_package():
    print(f"Building release package: {PKG_NAME}...")

    # Staging directory
    if PKG_DIR.exists():
        shutil.rmtree(PKG_DIR)
    PKG_DIR.mkdir()

    # Copy root files
    print("\n[1/3] Copying core flasher and documentation files...")
    for fname in ROOT_FILES:
        src = BASE_DIR / fname
        if not src.exists():
            print(f"[!] Error: missing required file {src}")
            sys.exit(1)
        shutil.copy2(src, PKG_DIR / fname)
        print(f"  + {fname} ({src.stat().st_size:,} bytes)")

    # Copy firmware components
    print("\n[2/3] Copying modular firmware binaries...")
    fw_dir = PKG_DIR / "firmware"
    fw_dir.mkdir()
    for name, src in FW_FILES:
        if not src.exists():
            print(f"[!] Error: missing firmware file {src}")
            sys.exit(1)
        shutil.copy2(src, fw_dir / name)
        print(f"  + firmware/{name} ({src.stat().st_size:,} bytes)")

    # Create Zip
    print(f"\n[3/3] Compressing into {ZIP_FILE.name}...")
    if ZIP_FILE.exists():
        ZIP_FILE.unlink()

    with zipfile.ZipFile(ZIP_FILE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(PKG_DIR):
            for f in sorted(files):
                full_path = Path(root) / f
                arcname = full_path.relative_to(BASE_DIR)
                zf.write(full_path, arcname=arcname)

    size = ZIP_FILE.stat().st_size
    sha256 = hashlib.sha256(ZIP_FILE.read_bytes()).hexdigest()

    print("\n========================================================")
    print(f" RELEASE PACKAGE GENERATED SUCCESSFULLY")
    print("========================================================")
    print(f" Archive:  {ZIP_FILE.name}")
    print(f" Size:     {size:,} bytes ({size / (1024*1024):.2f} MB)")
    print(f" SHA-256:  {sha256}")
    print("========================================================")

if __name__ == "__main__":
    make_package()
