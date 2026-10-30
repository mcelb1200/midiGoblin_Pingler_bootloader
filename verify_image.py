#!/usr/bin/env python3
"""
MIDI Goblin Dual Consolidated Image Verifier
============================================
Performs complete offline static verification of the 4MB consolidated flash image.
Validates all headers, checksums, hashes, partition tables, and disassembly without downloading anything.
"""

import struct
import hashlib
from pathlib import Path

IMAGE_PATH = Path(__file__).resolve().parent / "midigoblin_dual_consolidated.bin"

def verify_esp32_image(name, data, expected_entry=None):
    print(f"\n--- Verifying {name} ---")
    magic, seg_count, spi_mode, spi_speed_size, entry = struct.unpack('<BBBBI', data[:8])
    if magic != 0xE9:
        print(f" [FAIL] Invalid magic: {hex(magic)} (expected 0xE9)")
        return False

    mode_str = {0: "QIO", 1: "QOUT", 2: "DIO", 3: "DOUT"}.get(spi_mode, f"Unknown ({spi_mode})")
    print(f" Magic: 0x{magic:02X} (Valid ESP32)")
    print(f" Segments: {seg_count}")
    print(f" SPI Mode: {mode_str}")
    print(f" Entry point: 0x{entry:08X}")

    offset = 24
    chk = 0xEF
    for i in range(seg_count):
        laddr, slen = struct.unpack('<II', data[offset:offset+8])
        offset += 8
        sdata = data[offset:offset+slen]
        for b in sdata:
            chk ^= b
        offset += slen
        print(f"   Segment {i+1}: load 0x{laddr:08X}, len {slen:,} bytes (0x{slen:X})")

    # Checksum padding
    pad_len = 16 - ((offset + 1) % 16)
    chk_byte = data[offset + pad_len]
    chk_valid = (chk == chk_byte)
    print(f" Checksum byte: 0x{chk_byte:02X} (Calculated: 0x{chk:02X}) -> {'VALID [PASS]' if chk_valid else 'INVALID [FAIL]'}")

    # SHA256
    sha_offset = offset + pad_len + 1
    stored_sha = data[sha_offset : sha_offset + 32]
    calc_sha = hashlib.sha256(data[:sha_offset]).digest()
    sha_valid = (stored_sha == calc_sha)
    print(f" SHA-256 Hash: {stored_sha.hex()[:16]}... -> {'VALID [PASS]' if sha_valid else 'INVALID [FAIL]'}")

    return chk_valid and sha_valid

def parse_partition_table(data):
    print(f"\n--- Verifying Partition Table (0x8000) ---")
    PART_MAGIC = 0x50AA
    offset = 0
    count = 0
    while offset < len(data):
        entry_data = data[offset : offset + 32]
        if entry_data == b'\xFF' * 32 or len(entry_data) < 32:
            break
        magic, ptype, subtype, poffset, psize, label, flags = struct.unpack('<HBBII16sI', entry_data)
        if magic != PART_MAGIC:
            break
        label_str = label.split(b'\x00')[0].decode('ascii', errors='ignore')
        print(f"  Partition: {label_str:<10} Type: 0x{ptype:02X}, SubType: 0x{subtype:02X}, Offset: 0x{poffset:06X}, Size: {psize // 1024:>5} KB (0x{psize:X})")
        offset += 32
        count += 1
    return count > 0

def verify_bootloader_segment_layout(data):
    print("\n--- Verifying injected bootloader memory layout ---")
    if len(data) < 24 or data[0] != 0xE9:
        print(" [FAIL] Bootloader image header is missing or invalid.")
        return False, None

    segment_count = data[1]
    offset = 24
    segments = []
    for index in range(segment_count):
        if offset + 8 > len(data):
            print(f" [FAIL] Segment {index + 1} header is truncated.")
            return False, None
        load_addr, size = struct.unpack_from("<II", data, offset)
        offset += 8
        if offset + size > len(data):
            print(f" [FAIL] Segment {index + 1} data is truncated.")
            return False, None
        segments.append((load_addr, size))
        offset += size

    if len(segments) < 5:
        print(f" [FAIL] Expected code and DRAM-data segments; found {len(segments)} total segments.")
        return False, None

    code_addr, code_size = segments[3]
    data_addr, data_size = segments[4]
    code_ok = code_addr == 0x40081000 and code_size > 0
    data_ok = 0x3FFB0000 <= data_addr < 0x40000000 and data_size > 0
    print(f" Code: 0x{code_addr:08X}, {code_size:,} bytes -> {'VALID [PASS]' if code_ok else 'INVALID [FAIL]'}")
    print(f" Data: 0x{data_addr:08X}, {data_size:,} bytes -> {'VALID [PASS]' if data_ok else 'INVALID [FAIL]'}")
    return code_ok and data_ok, (code_addr, code_addr + code_size)

def main():
    print("========================================================")
    print(" MIDI Goblin Consolidated Image Offline Verification    ")
    print("========================================================")

    if not IMAGE_PATH.exists():
        print(f"File not found: {IMAGE_PATH}")
        return 1

    with open(IMAGE_PATH, "rb") as f:
        img = f.read()

    print(f"Total Image File Size: {len(img):,} bytes ({len(img)/(1024*1024):.2f} MB)")
    checks = [len(img) == 4 * 1024 * 1024]
    if not checks[-1]:
        print(" [FAIL] Expected a 4 MiB consolidated image.")

    # 1. Bootloader at 0x1000
    bl_data = img[0x1000 : 0x8000]
    checks.append(verify_esp32_image("Dual-Bootloader (0x1000)", bl_data))
    layout_ok, code_range = verify_bootloader_segment_layout(bl_data)
    checks.append(layout_ok)

    # Verify bootloader patch at 0x40080623
    # Segment 3 is at 0x40080400, file offset in image is 0x1000 + 24 + (8+1184) + (8+13260) + 8 = 0x489C
    # Target instruction is at 0x40080623 - 0x40080400 = 0x223 in segment 3
    seg3_img_offset = 0x1000 + 24 + 8 + 1184 + 8 + 13260 + 8
    patch_bytes = img[seg3_img_offset + 0x223 : seg3_img_offset + 0x223 + 3]
    print(f"\n Dual-Boot Branch Check at 0x40080623:")
    print(f"   Instruction bytes: {' '.join(f'0x{b:02X}' for b in patch_bytes)}")
    # Decode Xtensa call8: opcode 0x05 / 0x25 / etc.
    insn_val = patch_bytes[0] | (patch_bytes[1] << 8) | (patch_bytes[2] << 16)
    if (insn_val & 0x0F) == 0x05: # Xtensa CALL/CALLX family
        word_offset = (insn_val >> 6)
        if word_offset & 0x20000:
            word_offset -= 0x40000
        pc = 0x40080623
        target_addr = ((pc + 4) & ~3) + (word_offset * 4)
        branch_ok = code_range is not None and code_range[0] <= target_addr < code_range[1]
        print(f"   Target: call8 0x{target_addr:08X} (in injected IRAM code) -> {'VERIFIED [PASS]' if branch_ok else 'INVALID [FAIL]'}")
        checks.append(branch_ok)
    else:
        print(f"   [FAIL] Unexpected opcode at 0x40080623: {patch_bytes.hex()}")
        checks.append(False)

    # 2. Partition Table at 0x8000
    pt_data = img[0x8000 : 0x9000]
    checks.append(parse_partition_table(pt_data))

    # 3. App 0 (MIDI Goblin) at 0x10000
    app0_data = img[0x10000 : 0x150000]
    checks.append(verify_esp32_image("App 0: MIDI Goblin (0x10000)", app0_data))

    # 4. App 1 (Pingler) at 0x150000
    app1_data = img[0x150000 : 0x290000]
    checks.append(verify_esp32_image("App 1: Pingler (0x150000)", app1_data))

    # Memory Map Diagram
    print("\n========================================================")
    print(" FLASH MEMORY MAP:")
    print("  0x000000 - 0x001000 : ROM Reserved / Header")
    print("  0x001000 - 0x008000 : Dual-Bootloader with OLED & Button Select (28 KB)")
    print("  0x008000 - 0x009000 : Partition Table (4 KB)")
    print("  0x009000 - 0x00E000 : NVS Data Storage (20 KB)")
    print("  0x00E000 - 0x010000 : OTA Data Partition (8 KB)")
    print("  0x010000 - 0x150000 : [Slot 0] MIDI Goblin Firmware (1,280 KB)")
    print("  0x150000 - 0x290000 : [Slot 1] Pingler Firmware (1,280 KB)")
    print("  0x290000 - 0x3F0000 : SPIFFS Partition (1,408 KB)")
    print("  0x3F0000 - 0x400000 : Core Dump (64 KB)")
    print("========================================================")
    if all(checks):
        print(" ALL CHECKS PASSED: Image structure and bootloader memory layout are valid.\n")
        return 0
    print(" VERIFICATION FAILED: One or more image checks failed.\n")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
