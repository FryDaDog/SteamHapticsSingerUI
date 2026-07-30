# SteamHapticsSingerUI

![Latest Release](https://img.shields.io/github/v/release/FryDaDog/SteamHapticsSingerUI)
![License](https://img.shields.io/github/license/FryDaDog/SteamHapticsSingerUI)
![GitHub Repo stars](https://img.shields.io/github/stars/FryDaDog/SteamHapticsSingerUI)

A simple graphical user interface for **Steam Haptics Singer** by **CrazyCritic89**.

> **Linux only** for now. A Windows version is planned.

## Features

- ⭐ Favorites list for quick access to your songs
- ⚙️ Easily adjust Steam Haptics Singer command-line parameters
- ▶️ Play songs
- ⏹️ Stop playback
- 🔄 Restart playback

## Usage

1. Download the latest release.
2. Copy the `steam-haptics-ui` binary into the same folder as Steam Haptics Singer.
3. Open a terminal in that folder.
4. Make the binary executable:

```bash
chmod +x steam-haptics-ui
```

5. Run the application:

```bash
./steam-haptics-ui
```

## Building from Source

> This is only necessary if you want to build the application yourself.

### 1. Clone the repository

```bash
git clone https://github.com/FryDaDog/SteamHapticsSingerUI.git
cd SteamHapticsSingerUI
```



### 2. Install Tkinter

**Arch Linux**

```bash
sudo pacman -S tk
```

**Debian / Ubuntu**

```bash
sudo apt install python3-tk
```

### 3. Build

```bash
sh build.sh
```
## Planning to add

- Windows suport
- Installation script
- Autoupdates
  
## License

MIT License
