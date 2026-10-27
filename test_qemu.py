#!/usr/bin/env python3
"""
Automated QEMU Test for MIDI Goblin Dual-Bootloader
===================================================
Runs QEMU and tests both:
 1. Auto-boot countdown into MIDI Goblin (default)
 2. Interactive serial selection into Pingler ('python test_qemu.py pingler')
 3. Immediate selection into MIDI Goblin ('python test_qemu.py midigoblin')
"""

import sys
import time
import subprocess
from pathlib import Path

QEMU_EXE = Path(r"C:\Users\micha\.espressif\tools\qemu-xtensa\esp_develop_9.2.2_20250817\qemu\bin\qemu-system-xtensa.exe")
IMAGE_BIN = Path(r"C:\Users\micha\github\midigoblin-dual-loader\midigoblin_dual_consolidated.bin")

def run_test(test_name, input_keys=None, duration=6):
    print(f"\n========================================================")
    print(f" TEST RUN: {test_name}")
    print(f"========================================================")

    cmd = [
        str(QEMU_EXE),
        "-nographic",
        "-machine", "esp32",
        "-drive", f"file={IMAGE_BIN},if=mtd,format=raw"
    ]

    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if input_keys:
        time.sleep(0.8)
        p.stdin.write(input_keys)
        p.stdin.flush()

    time.sleep(duration)
    p.terminate()
    try:
        out, _ = p.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate()

    print(out)
    return out

if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "autoboot"
    if mode == "pingler":
        run_test("Interactive Key '2' -> Boot Pingler", input_keys="2\n", duration=5)
    elif mode in ["midigoblin", "goblin"]:
        run_test("Interactive Key '1' -> Boot MIDI Goblin", input_keys="1\n", duration=5)
    else:
        run_test("Auto-Boot Countdown (3s) -> MIDI Goblin", input_keys=None, duration=7)
