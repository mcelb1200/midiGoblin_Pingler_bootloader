# MIDI Goblin Dual-Bootloader & Consolidated Image

A dual-bootloader system for the **MIDI Goblin** hardware (ESP32) that allows selecting either **MIDI Goblin** or **Pingler** firmware at launch.

## Release v1.0.1

Hotfix for bootloader data placement and GPIO input setup. The injected boot menu constants load into DRAM, and the mux and encoder GPIO input buffers are enabled so hardware selection works before application firmware starts.

---

## Highlights

- **Custom Interactive 2nd-Stage Bootloader**: Executes in IRAM directly on ESP32 startup.
- The injected boot menu code runs from IRAM, while its strings and font data are loaded into DRAM for safe data access.
- **SH1106 OLED Display (128x64)**: Shows an interactive menu at power-on with countdown timer.
- **Hardware Navigation**:
  - **Rotary Encoder**: Rotate knob to toggle between MIDI Goblin and Pingler; push button to confirm and boot.
  - **Multiplexer Buttons**: Use Left/Up for MIDI Goblin, Down/Right for Pingler, Menu/Yes to confirm.
- **Fast-Boot Mode (Zero Wait)**:
  - Hold **Encoder Push Button**, **User 1**, **Right**, or the ESP32 **BOOT** button during power-on $\rightarrow$ immediately boots **Pingler**.
  - Hold **Left** or **User 2** button during power-on $\rightarrow$ immediately boots **MIDI Goblin**.
- **Serial / QEMU Console Input**: Press `1` for MIDI Goblin, `2` for Pingler, or Space/Enter to confirm.
- **Single Consolidated Binary**: `midigoblin_dual_consolidated.bin` (4MB) ready to flash to `0x00000000`.

---

## Flash Memory Map

| Address Range | Size | Partition | Description |
|---|---|---|---|
| `0x000000` - `0x001000` | 4 KB | ROM Header | ESP32 ROM boot header |
| `0x001000` - `0x008000` | 28 KB | Bootloader | Dual-bootloader with OLED & hardware select |
| `0x008000` - `0x009000` | 4 KB | Partition Table | Dual OTA partition table |
| `0x009000` - `0x00E000` | 20 KB | `nvs` | Non-volatile storage |
| `0x00E000` - `0x010000` | 8 KB | `otadata` | OTA state |
| `0x010000` - `0x150000` | 1,280 KB | `app0` (Slot 0) | **MIDI Goblin Firmware v1.0.5** |
| `0x150000` - `0x290000` | 1,280 KB | `app1` (Slot 1) | **Pingler Firmware v1.1** |
| `0x290000` - `0x3F0000` | 1,408 KB | `spiffs` | SPIFFS data filesystem |
| `0x3F0000` - `0x400000` | 64 KB | `coredump` | System core dump partition |

---

## Files

- [`midigoblin_dual_consolidated.bin`](./midigoblin_dual_consolidated.bin) — Consolidated 4MB image ready for hardware or QEMU.
- [`dual_bootloader.bin`](./dual_bootloader.bin) — Standalone dual bootloader image (flashed to `0x1000`).
- [`dual_boot.c`](./dual_boot.c) — Source code for the dual-bootloader selection and display logic.
- [`font5x7.h`](./font5x7.h) — 5x7 ASCII font table extracted from the original firmware.
- [`build.py`](./build.py) — Full build script that compiles C source, links against bootloader symbols, injects the routine, and creates the consolidated binary.
- [`verify_image.py`](./verify_image.py) — Zero-bandwidth offline verification tool that validates all segments, hashes, and disassembly.
- [`run_qemu.py`](./run_qemu.py) — QEMU test runner script.
- [`flash.py`](./flash.py) — Universal cross-platform flashing script (Windows, Linux, macOS).
- [`flash.sh`](./flash.sh) — Shell script wrapper for Linux and macOS.
- [`flash.bat`](./flash.bat) — Batch file wrapper for Windows.
- [`install_tools.bat`](./install_tools.bat) — Windows automated tool setup (`esptool`, `pyserial`).
- [`install_tools.sh`](./install_tools.sh) — Linux/macOS automated tool setup and `dialout` permission configuration.
- [`QUICKSTART.txt`](./QUICKSTART.txt) — Plain-text quick start guide.

---

## Tool Installation (One-Time Setup)

Before flashing for the first time, install the required tools:

### Windows
Double-click `install_tools.bat` or run:
```cmd
install_tools.bat
```

### Linux / macOS
Run the installer script:
```bash
bash install_tools.sh
```

---

## Flashing Target Hardware (Cross-Platform)

Connect your MIDI Goblin to your computer via USB, then run the appropriate script:

### Windows
```cmd
:: Interactive auto-detection
flash.bat

:: Or specify COM port
flash.bat -p COM3
```
*(Or via PowerShell / CMD: `python flash.py`)*

### Linux (Ubuntu, Debian, Fedora, Arch)
```bash
# Make script executable (first time only)
chmod +x flash.sh

# Interactive auto-detection
./flash.sh

# Or specify port
./flash.sh -p /dev/ttyUSB0
```
> **Note for Linux**: If you encounter permission errors accessing `/dev/ttyUSB0`, ensure your user is in the `dialout` group:
> ```bash
> sudo usermod -a -G dialout $USER
> # Then log out and log back in
> ```

### macOS (Intel & Apple Silicon M1/M2/M3/M4)
```bash
# Make script executable (first time only)
chmod +x flash.sh

# Interactive auto-detection
./flash.sh

# Or specify port (use the /dev/cu.* device node)
./flash.sh -p /dev/cu.usbserial-0001
```

### Useful Flashing Options
- **List detected serial ports**:
  ```bash
  python flash.py --list
  ```
- **Erase flash before writing**:
  ```bash
  python flash.py --erase
  ```
- **Flash individual components** (from `firmware/` folder):
  ```bash
  python flash.py --component bootloader   # Only flash bootloader to 0x1000
  python flash.py --component midigoblin   # Only flash MIDI Goblin to 0x10000
  python flash.py --component pingler      # Only flash Pingler to 0x150000
  python flash.py --component parts        # Flash all 5 separate components
  ```
- **Use lower baud rate (if cable is noisy)**:
  ```bash
  python flash.py -b 115200
  ```

---

## Testing with QEMU

To run with Espressif QEMU:

```powershell
python run_qemu.py
```

If QEMU is not yet installed on your machine, it can be installed (requires ~35 MB download) with:
```powershell
& "~\.espressif\python_env\idf6.0_py3.13_env\Scripts\python.exe" "~\.espressif\v6.0.1\esp-idf\tools\idf_tools.py" install qemu-xtensa
```
