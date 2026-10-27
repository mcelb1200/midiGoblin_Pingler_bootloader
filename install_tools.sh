#!/usr/bin/env bash
# ==============================================================================
# MIDI Goblin Tool Installer (Linux & macOS)
# ==============================================================================
# Automatically sets up Python 3, esptool, and serial permissions.
# ==============================================================================

set -e

OS_NAME="$(uname -s)"
echo "========================================================"
echo " MIDI Goblin Tools Setup ($OS_NAME)"
echo "========================================================"
echo ""

if [ "$OS_NAME" = "Linux" ]; then
    echo "[1/3] Checking Linux packages..."
    if command -v apt-get >/dev/null 2>&1; then
        echo "Updating apt and installing python3, pip, and serial support..."
        sudo apt-get update -qq || true
        sudo apt-get install -y python3 python3-pip python3-serial || true
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-pip python3-pyserial || true
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --noconfirm python python-pip python-pyserial || true
    fi

    echo ""
    echo "[2/3] Installing esptool and pyserial via pip..."
    pip3 install --user --upgrade esptool pyserial || pip install --user --upgrade esptool pyserial || sudo apt-get install -y esptool

    echo ""
    echo "[3/3] Setting up USB Serial device permissions..."
    CURRENT_USER="$(whoami)"
    if groups "$CURRENT_USER" | grep -q "dialout"; then
        echo "User '$CURRENT_USER' is already in 'dialout' group."
    else
        echo "Adding '$CURRENT_USER' to 'dialout' group..."
        sudo usermod -a -G dialout "$CURRENT_USER" || sudo usermod -a -G uucp "$CURRENT_USER" || true
        echo "Note: You may need to log out and back in for serial group permissions to take effect."
    fi

elif [ "$OS_NAME" = "Darwin" ]; then
    echo "[1/2] Checking macOS Python installation..."
    if ! command -v python3 >/dev/null 2>&1; then
        if command -v brew >/dev/null 2>&1; then
            echo "Installing Python via Homebrew..."
            brew install python
        else
            echo "[!] Python 3 not found. Please install Python 3 from https://www.python.org/downloads/macos/"
            exit 1
        fi
    fi

    echo ""
    echo "[2/2] Installing esptool and pyserial..."
    python3 -m pip install --user --upgrade esptool pyserial

else
    echo "Unsupported OS: $OS_NAME"
    exit 1
fi

echo ""
echo "========================================================"
echo " SUCCESS: Flashing tools are installed and ready!"
echo " You can now run: ./flash.sh"
echo "========================================================"
