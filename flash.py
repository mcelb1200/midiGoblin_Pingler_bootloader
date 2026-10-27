#!/usr/bin/env python3
"""
MIDI Goblin Dual Consolidated Firmware Flasher
==============================================
Cross-Platform flashing tool for Windows, Linux, and macOS.
Flashes midigoblin_dual_consolidated.bin directly to offset 0x0.

Usage:
  python flash.py               (Interactive mode - auto-detects port)
  python flash.py -p COM3       (Windows: specify port)
  python flash.py -p /dev/ttyUSB0 (Linux: specify port)
  python flash.py -p /dev/cu.usbserial-0001 (macOS: specify port)
  python flash.py --erase       (Erase entire flash before writing)
  python flash.py --list        (List detected serial ports)
  python flash.py --install     (Install/upgrade esptool & pyserial via pip)
"""

import os
import sys
import glob
import shutil
import platform
import argparse
import subprocess
from pathlib import Path

DEFAULT_BAUD = 921600
IMAGE_FILENAME = "midigoblin_dual_consolidated.bin"
SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE_PATH = SCRIPT_DIR / IMAGE_FILENAME

# Common USB-to-UART vendor/product IDs used on ESP32 DevKits
KNOWN_ESP_VID_PID = [
    (0x10C4, 0xEA60),  # Silicon Labs CP210x
    (0x1A86, 0x7523),  # WCH CH340
    (0x1A86, 0x55D4),  # WCH CH9102
    (0x0403, 0x6001),  # FTDI FT232R
    (0x0403, 0x6010),  # FTDI Dual
    (0x303A, 0x1001),  # Espressif USB-JTAG/Serial
    (0x303A, 0x0002),  # Espressif ESP32-S2
]

def get_platform_name():
    system = platform.system()
    if system == "Windows":
        return "Windows"
    elif system == "Darwin":
        return "macOS"
    elif system == "Linux":
        return "Linux"
    return system

def list_serial_ports():
    """Returns a list of tuples: (port_device, description, is_probable_esp)"""
    results = []
    
    # 1. Try pyserial if available
    try:
        import serial.tools.list_ports
        for port in serial.tools.list_ports.comports():
            desc = port.description or ""
            is_esp = False
            if port.vid and port.pid:
                for kvid, kpid in KNOWN_ESP_VID_PID:
                    if port.vid == kvid and port.pid == kpid:
                        is_esp = True
                        break
            if any(k in desc.lower() for k in ["cp210", "ch340", "ch910", "ftdi", "uart", "usb serial", "espressif"]):
                is_esp = True
            results.append((port.device, desc, is_esp))
        if results:
            return results
    except ImportError:
        pass

    # 2. Fallback to OS-specific enumeration
    system = platform.system()
    if system == "Darwin":
        # On macOS, prefer /dev/cu.* over /dev/tty.*
        matches = glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.usbmodem*") + \
                  glob.glob("/dev/cu.SLAB_USBtoUART*") + glob.glob("/dev/cu.wchusbserial*")
        for m in sorted(set(matches)):
            results.append((m, "USB Serial Device", True))
    elif system == "Linux":
        matches = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
        for m in sorted(set(matches)):
            results.append((m, "USB Serial Device", True))
    elif system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
            for i in range(128):
                try:
                    val_name, port_name, _ = winreg.EnumValue(key, i)
                    results.append((port_name, val_name, True))
                except OSError:
                    break
            winreg.CloseKey(key)
        except Exception:
            pass

    return results

def choose_port(explicit_port=None):
    if explicit_port:
        return explicit_port

    ports = list_serial_ports()

    if not ports:
        print("\n[!] No serial ports detected!")
        system = get_platform_name()
        print("\nTroubleshooting tips for " + system + ":")
        if system == "Windows":
            print("  1. Ensure your MIDI Goblin / ESP32 is plugged in via a USB data cable.")
            print("  2. Check Device Manager under 'Ports (COM & LPT)'.")
            print("  3. If you see a yellow exclamation mark, install the CP210x or CH340 driver.")
        elif system == "Linux":
            print("  1. Ensure your device is plugged in.")
            print("  2. Check 'dmesg | grep -i tty' to see if the device was assigned /dev/ttyUSB0.")
            print("  3. Permission check: add your user to dialout group:")
            print("       sudo usermod -a -G dialout $USER")
            print("       (Log out and back in for changes to take effect)")
        elif system == "macOS":
            print("  1. Ensure your device is plugged in.")
            print("  2. Check 'ls /dev/cu.*' in Terminal.")
            print("  3. If using CH340 or CP210x chips, install the respective macOS VCP driver.")
        print()
        sys.exit(1)

    # If only 1 port found, auto-select it
    if len(ports) == 1:
        dev, desc, _ = ports[0]
        print(f"Auto-detected port: {dev} ({desc})")
        return dev

    # If multiple ports, present interactive menu
    print("\nMultiple serial ports detected:")
    esp_candidates = []
    for idx, (dev, desc, is_esp) in enumerate(ports, 1):
        tag = " [Likely ESP32/MIDI Goblin]" if is_esp else ""
        print(f"  [{idx}] {dev} - {desc}{tag}")
        if is_esp:
            esp_candidates.append(idx)

    default_idx = esp_candidates[0] if len(esp_candidates) == 1 else 1

    try:
        user_input = input(f"\nSelect port [default: {default_idx}]: ").strip()
        if not user_input:
            chosen = default_idx
        else:
            chosen = int(user_input)
        if 1 <= chosen <= len(ports):
            return ports[chosen - 1][0]
        else:
            print("Invalid selection. Exiting.")
            sys.exit(1)
    except (ValueError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(1)

def find_esptool():
    # 1. Try python module `esptool`
    try:
        import esptool
        return [sys.executable, "-m", "esptool"]
    except ImportError:
        pass

    # 2. Check PATH for `esptool.py` or `esptool`
    for exe in ["esptool.py", "esptool"]:
        found = shutil.which(exe)
        if found:
            return [found]

    # 3. Check PlatformIO tool-esptoolpy
    home = Path.home()
    pio_esptool = home / ".platformio" / "packages" / "tool-esptoolpy" / "esptool.py"
    if pio_esptool.exists():
        for py in [sys.executable, home / ".platformio" / "penv" / "Scripts" / "python.exe", home / ".platformio" / "penv" / "bin" / "python"]:
            if Path(py).exists():
                return [str(py), str(pio_esptool)]
        return [sys.executable, str(pio_esptool)]

    # 4. Check ESP-IDF esptool
    idf_esptool = home / ".espressif" / "v6.0.1" / "esp-idf" / "components" / "esptool_py" / "esptool" / "esptool.py"
    if idf_esptool.exists():
        return [sys.executable, str(idf_esptool)]

    return None

def install_esptool_via_pip():
    print("\nAttempting to install 'esptool' and 'pyserial' via pip...")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "esptool", "pyserial"]
    try:
        res = subprocess.run(cmd)
        if res.returncode == 0:
            print("[+] Successfully installed esptool and pyserial!")
            return True
        else:
            print(f"[!] pip install returned error code {res.returncode}")
            return False
    except Exception as e:
        print(f"[!] Could not run pip: {e}")
        return False

def ensure_esptool():
    cmd = find_esptool()
    if cmd:
        return cmd

    print("\n" + "=" * 56)
    print(" [!] 'esptool' is required to flash the ESP32.")
    print("     It is not currently found in your Python environment.")
    print("=" * 56)
    try:
        ans = input("Would you like to install it automatically now via pip? [Y/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        ans = "n"

    if ans in ["", "y", "yes"]:
        if install_esptool_via_pip():
            cmd = find_esptool()
            if cmd:
                return cmd

    print("\nPlease manually install esptool by running:")
    print("  pip install esptool pyserial")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="MIDI Goblin Dual Consolidated Firmware Flasher (Cross-Platform)"
    )
    parser.add_argument("-p", "--port", help="Serial port (e.g. COM3, /dev/ttyUSB0, /dev/cu.usbserial-0001)")
    parser.add_argument("-b", "--baud", type=int, default=DEFAULT_BAUD, help=f"Baud rate (default: {DEFAULT_BAUD})")
    parser.add_argument("-i", "--image", default=str(IMAGE_PATH), help=f"Firmware binary (default: {IMAGE_FILENAME})")
    parser.add_argument("--component", choices=["consolidated", "parts", "bootloader", "midigoblin", "pingler"], default="consolidated",
                        help="Select component to flash (default: consolidated 4MB image)")
    parser.add_argument("--erase", action="store_true", help="Erase entire flash chip before flashing")
    parser.add_argument("--list", action="store_true", help="List detected serial ports and exit")
    parser.add_argument("--install", action="store_true", help="Install/upgrade esptool & pyserial via pip")
    args = parser.parse_args()

    print("========================================================")
    print(" MIDI Goblin Dual Consolidated Firmware Flasher         ")
    print(f" OS: {get_platform_name()} ({platform.machine()})")
    print("========================================================")

    if args.install:
        install_esptool_via_pip()
        return

    if args.list:
        ports = list_serial_ports()
        print("\nDetected Serial Ports:")
        if not ports:
            print("  (None found)")
        for dev, desc, is_esp in ports:
            tag = " [ESP32 Candidate]" if is_esp else ""
            print(f"  - {dev:<20} {desc}{tag}")
        return

    fw_dir = SCRIPT_DIR / "firmware"

    # Determine files and offsets based on component selection
    flash_pairs = []
    if args.component == "consolidated":
        image_file = Path(args.image)
        if not image_file.exists():
            print(f"\n[ERROR] Firmware image not found: {image_file}")
            print("Please ensure 'midigoblin_dual_consolidated.bin' is in the same folder.")
            sys.exit(1)
        img_size = image_file.stat().st_size
        print(f" Firmware Image: {image_file.name} ({img_size:,} bytes / {img_size/(1024*1024):.2f} MB)")
        flash_pairs = [("0x0", str(image_file))]
    elif args.component == "bootloader":
        bl_file = fw_dir / "dual_bootloader.bin"
        if not bl_file.exists(): bl_file = SCRIPT_DIR / "dual_bootloader.bin"
        if not bl_file.exists():
            print(f"[ERROR] Bootloader binary not found: {bl_file}")
            sys.exit(1)
        print(f" Flashing Bootloader only: {bl_file.name} to 0x1000")
        flash_pairs = [("0x1000", str(bl_file))]
    elif args.component == "midigoblin":
        app0_file = fw_dir / "midi_goblin1_0_5.ino.bin"
        if not app0_file.exists(): app0_file = SCRIPT_DIR / "midi_goblin1_0_5.ino.bin"
        if not app0_file.exists():
            print(f"[ERROR] MIDI Goblin binary not found: {app0_file}")
            sys.exit(1)
        print(f" Flashing MIDI Goblin (App 0) only: {app0_file.name} to 0x10000")
        flash_pairs = [("0x10000", str(app0_file))]
    elif args.component == "pingler":
        app1_file = fw_dir / "MIDI_Goblin_Pingler_v_1_1.bin"
        if not app1_file.exists(): app1_file = SCRIPT_DIR / "MIDI_Goblin_Pingler_v_1_1.bin"
        if not app1_file.exists():
            print(f"[ERROR] Pingler binary not found: {app1_file}")
            sys.exit(1)
        print(f" Flashing Pingler (App 1) only: {app1_file.name} to 0x150000")
        flash_pairs = [("0x150000", str(app1_file))]
    elif args.component == "parts":
        req_files = [
            ("0x1000", fw_dir / "dual_bootloader.bin"),
            ("0x8000", fw_dir / "partitions.bin"),
            ("0xe000", fw_dir / "boot_app0.bin"),
            ("0x10000", fw_dir / "midi_goblin1_0_5.ino.bin"),
            ("0x150000", fw_dir / "MIDI_Goblin_Pingler_v_1_1.bin"),
        ]
        for off, path in req_files:
            if not path.exists():
                print(f"[ERROR] Required modular component not found: {path}")
                sys.exit(1)
            flash_pairs.append((off, str(path)))
        print(f" Flashing 5 individual components from {fw_dir.name}/")

    # Ensure esptool is available
    esptool_cmd = ensure_esptool()

    # Select serial port
    target_port = choose_port(args.port)
    print(f" Target Port:    {target_port}")
    print(f" Baud Rate:      {args.baud}")

    # Optional chip erase
    if args.erase:
        print("\n[1/2] Erasing flash chip...")
        erase_cmd = esptool_cmd + ["--chip", "esp32", "-p", target_port, "-b", str(args.baud), "erase_flash"]
        res = subprocess.run(erase_cmd)
        if res.returncode != 0:
            print("[ERROR] Flash erase failed.")
            sys.exit(res.returncode)

    # Flash write
    print("\nWriting firmware...")
    flash_cmd = esptool_cmd + [
        "--chip", "esp32",
        "-p", target_port,
        "-b", str(args.baud),
        "--before", "default_reset",
        "--after", "hard_reset",
        "write_flash",
        "-z",
        "--flash_mode", "dio",
        "--flash_freq", "80m",
        "--flash_size", "4MB",
    ]
    for off, path in flash_pairs:
        flash_cmd.extend([off, path])

    res = subprocess.run(flash_cmd)
    if res.returncode == 0:
        print("\n========================================================")
        print(" SUCCESS! MIDI Goblin Dual Firmware flashed successfully!")
        print("========================================================")
        print("The device will now reboot into the Dual-Bootloader.")
        print("At power-on:")
        print("  - Use Rotary Encoder or Buttons to choose firmware.")
        print("  - Or hold Encoder/BOOT button for instant Pingler boot.")
        print("========================================================\n")
    else:
        print("\n[ERROR] Flashing failed (exit code: %d)." % res.returncode)
        print("\nTroubleshooting connection issues:")
        print("  1. If you see 'Failed to connect to ESP32: Timed out waiting for packet header':")
        print("     -> Press and HOLD the BOOT button on the ESP32 while re-running flash.")
        print("     -> Release the button when 'Connecting...' appears.")
        print("  2. Try a lower baud rate: python flash.py -b 115200")
        print("  3. Make sure no other application (Serial monitor, DAW, Arduino) is using the port.")
        sys.exit(res.returncode)

if __name__ == "__main__":
    main()
