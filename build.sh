#!/usr/bin/env bash
# build.sh - packages steam_haptics_ui.py into a single standalone binary
#
# Run this on your own Linux machine (not in a sandbox), in the same
# folder as steam_haptics_ui.py. Needs python3, pip, and tkinter.

set -e

if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "tkinter isn't installed. On Debian/Ubuntu:"
    echo "  sudo apt install python3-tk"
    exit 1
fi

if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install --user pyinstaller
fi

python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name steam-haptics-ui \
    steam_haptics_ui.py

echo ""
echo "Done. Binary is at: dist/steam-haptics-ui"
