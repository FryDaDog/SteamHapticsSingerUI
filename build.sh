#!/usr/bin/env bash
#
# build.sh
#
# Builds steam_haptics_ui.py into a standalone binary.
# Uses a local Python virtual environment.

set -euo pipefail

if ! python -c "import tkinter" 2>/dev/null; then
    echo "tkinter isn't installed. On Debian/Ubuntu:"
    echo "  sudo apt install python3-tk"
    echo "On Arch:"
    echo "  sudo pacman -S tk"
    exit 1
fi

APP_NAME="steam-haptics-ui"
ENTRYPOINT="steam_haptics_ui.py"
VENV=".venv"

echo "==> Cleaning previous builds..."
rm -rf build dist __pycache__
rm -f "${APP_NAME}.spec"

if [[ ! -d "$VENV" ]]; then
    echo "==> Creating virtual environment..."
    python -m venv "$VENV"
fi

echo "==> Activating virtual environment..."
source "$VENV/bin/activate"

echo "==> Updating pip..."
python -m pip install --upgrade pip wheel

echo "==> Installing build dependencies..."
python -m pip install --upgrade pyinstaller

echo "==> Building..."
pyinstaller \
    --clean \
    --noconfirm \
    --onefile \
    --windowed \
    --name "$APP_NAME" \
    --add-data "SteamHapticsLogo.png:." \
    "$ENTRYPOINT"

if command -v strip >/dev/null; then
    echo "==> Stripping symbols..."
    strip "dist/$APP_NAME" || true
fi

if command -v upx >/dev/null; then
    echo "==> Compressing binary with UPX..."
    upx --best --lzma "dist/$APP_NAME" || true
fi

echo
echo "Build complete!"
echo "Binary: dist/$APP_NAME"
