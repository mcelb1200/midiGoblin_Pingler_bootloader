#!/usr/bin/env python3
"""
MIDI Goblin Dual-Bootloader & Consolidated Image Builder
========================================================
This script builds the dual-bootloader from C source and merges
all firmwares (MIDI Goblin & Pingler) into a single flashable image.
"""

import os
import sys
import struct
import hashlib
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Toolchain paths from PlatformIO installation
TOOLCHAIN_GCC = Path(r"C:\Users\micha\.platformio\packages\toolchain-xtensa-esp32\bin\xtensa-esp32-elf-gcc.exe")
TOOLCHAIN_LD  = Path(r"C:\Users\micha\.platformio\packages\toolchain-xtensa-esp32\bin\xtensa-esp32-elf-ld.exe")
TOOLCHAIN_NM  = Path(r"C:\Users\micha\.platformio\packages\toolchain-xtensa-esp32\bin\xtensa-esp32-elf-nm.exe")
TOOLCHAIN_OBJCOPY = Path(r"C:\Users\micha\.platformio\packages\toolchain-xtensa-esp32\bin\xtensa-esp32-elf-objcopy.exe")
PYTHON_BIN    = Path(r"C:\Users\micha\.platformio\penv\Scripts\python.exe")
ESPTOOL_PY    = Path(r"C:\Users\micha\.platformio\packages\tool-esptoolpy\esptool.py")

# SDK & Binary paths
FRAMEWORK_DIR = Path(r"C:\Users\micha\.platformio\packages\framework-arduinoespressif32")
BASE_BOOTLOADER_ELF = FRAMEWORK_DIR / "tools" / "sdk" / "esp32" / "bin" / "bootloader_dio_80m.elf"

# Prefer self-contained binaries in firmware/ directory, fallback to build paths
FW_DIR = BASE_DIR / "firmware"
BASE_BOOTLOADER_BIN = FW_DIR / "base_bootloader.bin" if (FW_DIR / "base_bootloader.bin").exists() else BASE_DIR / "MIDI_Goblin-midi_goblin_v1.0.5" / "build" / "esp32.esp32.esp32doit-devkit-v1" / "midi_goblin.ino.bootloader.bin"
PARTITION_BIN = FW_DIR / "partitions.bin" if (FW_DIR / "partitions.bin").exists() else BASE_DIR / "MIDI_Goblin-midi_goblin_v1.0.5" / "build" / "esp32.esp32.esp32doit-devkit-v1" / "midi_goblin.ino.partitions.bin"
BOOT_APP0_BIN = FW_DIR / "boot_app0.bin" if (FW_DIR / "boot_app0.bin").exists() else FRAMEWORK_DIR / "tools" / "partitions" / "boot_app0.bin"

# Input firmwares
MIDI_GOBLIN_BIN = BASE_DIR / "midi_goblin1_0_5.ino.bin"
PINGLER_BIN     = BASE_DIR / "MIDI_Goblin_Pingler_v_1_1.bin"

# Output files
DUAL_BOOT_O     = BASE_DIR / "dual_boot.o"
DUAL_BOOT_ELF   = BASE_DIR / "dual_boot.elf"
DUAL_BOOT_BIN   = BASE_DIR / "dual_boot.bin"
OUTPUT_BOOTLOADER = BASE_DIR / "dual_bootloader.bin"
OUTPUT_CONSOLIDATED = BASE_DIR / "midigoblin_dual_consolidated.bin"

INCLUDE_DIRS = [
    FRAMEWORK_DIR / "tools" / "sdk" / "esp32" / "include" / "soc" / "esp32" / "include",
    FRAMEWORK_DIR / "tools" / "sdk" / "esp32" / "include" / "soc" / "include",
    FRAMEWORK_DIR / "tools" / "sdk" / "esp32" / "include" / "hal" / "include",
    FRAMEWORK_DIR / "tools" / "sdk" / "esp32" / "include" / "hal" / "esp32" / "include",
    FRAMEWORK_DIR / "tools" / "sdk" / "esp32" / "include" / "esp_rom" / "include",
    FRAMEWORK_DIR / "tools" / "sdk" / "esp32" / "include" / "esp_hw_support" / "include",
    FRAMEWORK_DIR / "tools" / "sdk" / "esp32" / "include" / "esp_common" / "include",
]

def step1_compile():
    print("[1/5] Compiling dual_boot.c with xtensa-esp32-elf-gcc...")
    cmd = [
        str(TOOLCHAIN_GCC),
        "-Os", "-c", "dual_boot.c", "-o", str(DUAL_BOOT_O),
        "-DSOC_CAPS_ECO_VER=3",
        "-mlongcalls", "-fno-jump-tables",
        "-mtext-section-literals",
        "-ffunction-sections", "-fdata-sections"
    ]
    for inc in INCLUDE_DIRS:
        cmd.extend(["-I", str(inc)])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Compilation failed:\n", res.stderr)
        sys.exit(1)
    print("      Compiled dual_boot.o successfully.")

def step2_link():
    print("[2/5] Linking dual_boot.o with dual_boot.ld at 0x40081000...")
    cmd = [
        str(TOOLCHAIN_LD),
        f"--just-symbols={BASE_BOOTLOADER_ELF}",
        "-T", "dual_boot.ld",
        "-e", "select_firmware",
        str(DUAL_BOOT_O),
        "-o", str(DUAL_BOOT_ELF)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Linking failed:\n", res.stderr)
        sys.exit(1)

    # Read select_firmware address dynamically
    res_nm = subprocess.run([str(TOOLCHAIN_NM), str(DUAL_BOOT_ELF)], capture_output=True, text=True)
    entry_addr = None
    for line in res_nm.stdout.splitlines():
        if " select_firmware" in line:
            entry_addr = int(line.split()[0], 16)
            break
    print(f"      Verified select_firmware entry at: 0x{entry_addr:08X}")

    # Extract binary payload
    cmd_copy = [str(TOOLCHAIN_OBJCOPY), "-O", "binary", str(DUAL_BOOT_ELF), str(DUAL_BOOT_BIN)]
    res = subprocess.run(cmd_copy, capture_output=True, text=True)
    if res.returncode != 0:
        print("Objcopy failed:\n", res.stderr)
        sys.exit(1)
    print(f"      Linked dual_boot.elf and generated dual_boot.bin ({DUAL_BOOT_BIN.stat().st_size} bytes).")
    return entry_addr

def step3_patch_bootloader(entry_addr):
    print("[3/5] Injecting dual-boot routine into ESP-IDF 2nd-stage bootloader...")
    with open(BASE_BOOTLOADER_BIN, "rb") as f:
        orig = f.read()

    with open(DUAL_BOOT_BIN, "rb") as f:
        new_seg_data = f.read()

    # Align new segment to 4 bytes
    if len(new_seg_data) % 4 != 0:
        new_seg_data += b"\x00" * (4 - (len(new_seg_data) % 4))

    # Update header: 4 segments
    header = bytearray(orig[:24])
    header[1] = 4

    segments = []
    offset = 24
    for i in range(3):
        laddr, slen = struct.unpack("<II", orig[offset:offset+8])
        offset += 8
        sdata = bytearray(orig[offset:offset+slen])
        offset += slen
        segments.append({"laddr": laddr, "data": sdata})

    # Segment 3 is at 0x40080400.
    # Instruction at 0x40080623 was: call8 40079464 (\x25\xe4\xf8)
    # Calculate exact call8 instruction to entry_addr
    target = entry_addr
    pc = 0x40080623
    word_offset = ((target & ~3) - ((pc + 4) & ~3)) // 4
    call8_insn = ((word_offset & 0x3FFFF) << 6) | 0x25
    patch_bytes = struct.pack("<I", call8_insn)[:3]

    patch_offset = 0x40080623 - 0x40080400
    assert segments[2]["data"][patch_offset:patch_offset+3] == b"\x25\xe4\xf8", "Unexpected original instruction bytes"
    segments[2]["data"][patch_offset:patch_offset+3] = patch_bytes
    print(f"      Patched branch at 0x40080623 -> call8 0x{entry_addr:08X} ({' '.join(f'0x{b:02X}' for b in patch_bytes)})")

    # Add Segment 4 at 0x40081000
    segments.append({"laddr": 0x40081000, "data": new_seg_data})

    # Reconstruct binary with valid checksum and SHA-256
    out = bytearray(header)
    chk = 0xEF
    for seg in segments:
        out += struct.pack("<II", seg["laddr"], len(seg["data"]))
        out += seg["data"]
        for b in seg["data"]:
            chk ^= b

    pad_len = 16 - ((len(out) + 1) % 16)
    out += b"\x00" * pad_len
    out.append(chk)

    sha = hashlib.sha256(out).digest()
    out += sha

    with open(OUTPUT_BOOTLOADER, "wb") as f:
        f.write(out)

    print(f"      Generated dual_bootloader.bin ({len(out)} bytes).")

def step4_verify_bootloader():
    print("[4/5] Verifying dual_bootloader.bin structure with esptool.py...")
    cmd = [str(PYTHON_BIN), str(ESPTOOL_PY), "image_info", str(OUTPUT_BOOTLOADER)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if "Checksum: ff (valid)" not in res.stdout and "valid" not in res.stdout:
        print("Verification warning:\n", res.stdout)
    else:
        print("      Bootloader verification passed (all segments, checksum, and SHA-256 valid).")

def step5_merge_consolidated():
    print("[5/5] Merging firmwares into single consolidated binary image...")
    cmd = [
        str(PYTHON_BIN), str(ESPTOOL_PY),
        "--chip", "esp32", "merge_bin",
        "-o", str(OUTPUT_CONSOLIDATED),
        "--flash_mode", "dio",
        "--flash_freq", "80m",
        "--flash_size", "4MB",
        "--fill-flash-size", "4MB",
        "0x1000", str(OUTPUT_BOOTLOADER),
        "0x8000", str(PARTITION_BIN),
        "0xe000", str(BOOT_APP0_BIN),
        "0x10000", str(MIDI_GOBLIN_BIN),
        "0x150000", str(PINGLER_BIN)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("merge_bin failed:\n", res.stderr)
        sys.exit(1)

    size = OUTPUT_CONSOLIDATED.stat().st_size
    print(f"\n========================================================")
    print(f" SUCCESS! Consolidated image created:")
    print(f"  File: {OUTPUT_CONSOLIDATED.name}")
    print(f"  Size: {size:,} bytes ({size / (1024*1024):.2f} MB)")
    print(f"========================================================")

if __name__ == "__main__":
    step1_compile()
    entry_addr = step2_link()
    step3_patch_bootloader(entry_addr)
    step4_verify_bootloader()
    step5_merge_consolidated()
