#!/usr/bin/env bash
# ==============================================================================
# MIDI Goblin Dual Consolidated Firmware Flasher (Linux & macOS)
# ==============================================================================
# Usage:
#   ./flash.sh                     (Auto-detect port and flash)
#   ./flash.sh -p /dev/ttyUSB0     (Specify Linux port)
#   ./flash.sh -p /dev/cu.usbserial-0001 (Specify macOS port)
#   ./flash.sh --erase             (Erase chip before flashing)
#   ./flash.sh --list              (List detected serial ports)
# ==============================================================================

set -e

# Resolve directory of this script (handles symlinks)
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

OS_NAME="$(uname -s)"

# Check for python3 or python
PYTHON=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
fi

if [ -n "$PYTHON" ]; then
    exec "$PYTHON" "$SCRIPT_DIR/flash.py" "$@"
fi

# Fallback if Python is not installed
echo "========================================================"
echo " MIDI Goblin Dual Consolidated Firmware Flasher"
echo " OS: $OS_NAME"
echo "========================================================"
echo ""
echo "[!] Python 3 was not found in your PATH."
echo "Please install Python 3 and esptool:"

if [ "$OS_NAME" = "Darwin" ]; then
    echo "  brew install python esptool"
elif [ "$OS_NAME" = "Linux" ]; then
    echo "  sudo apt install python3 python3-pip"
    echo "  pip install esptool"
fi

exit 1
