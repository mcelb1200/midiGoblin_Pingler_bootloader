#!/usr/bin/env python3
"""
MIDI Goblin Dual-Bootloader QEMU Interactive Launcher
=====================================================
Launches Espressif QEMU with the 4MB consolidated flash image.
"""

import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONSOLIDATED_IMAGE = BASE_DIR / "midigoblin_dual_consolidated.bin"

# Standard paths where ESP-IDF installs qemu-xtensa
QEMU_PATHS = [
    Path(r"C:\Users\micha\.espressif\tools\qemu-xtensa\esp_develop_9.2.2_20250817\qemu\bin\qemu-system-xtensa.exe"),
    Path(r"C:\Users\micha\.espressif\tools\qemu-xtensa"),
]

def find_qemu():
    for p in QEMU_PATHS:
        if p.is_file() and p.exists():
            return p
        if p.is_dir() and p.exists():
            for exe in p.rglob("qemu-system-xtensa.exe"):
                return exe

    qemu_cmd = shutil.which("qemu-system-xtensa")
    if qemu_cmd:
        return Path(qemu_cmd)

    return None

def main():
    print("====================================================")
    print("  MIDI Goblin Dual-Bootloader - QEMU Launcher       ")
    print("====================================================\n")

    if not CONSOLIDATED_IMAGE.exists():
        print(f"Error: Consolidated image '{CONSOLIDATED_IMAGE.name}' not found!")
        print("Please run 'python build.py' first.")
        sys.exit(1)

    qemu_exe = find_qemu()
    if not qemu_exe:
        print("[!] QEMU (qemu-system-xtensa) not found.")
        sys.exit(1)

    print(f"Found QEMU at: {qemu_exe}")
    print(f"Starting QEMU with image: {CONSOLIDATED_IMAGE.name} (4MB)")
    print("\nControls in QEMU Console:")
    print("  - Press '1' or 'm' -> Boot MIDI Goblin immediately")
    print("  - Press '2' or 'p' -> Boot Pingler immediately")
    print("  - Press Space/Enter -> Confirm highlighted choice")
    print("  - Wait 3 seconds -> Auto-boots default (MIDI Goblin)")
    print("  - To exit QEMU: Press Ctrl+A, then X\n")
    print("----------------------------------------------------\n")

    cmd = [
        str(qemu_exe),
        "-nographic",
        "-machine", "esp32",
        "-drive", f"file={CONSOLIDATED_IMAGE},if=mtd,format=raw"
    ]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nQEMU stopped.")

if __name__ == "__main__":
    main()
