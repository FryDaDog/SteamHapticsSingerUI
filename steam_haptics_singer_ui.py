
#!/usr/bin/env python3
# steam_haptics_ui.py
#
# GUI wrapper around the steam-haptics-singer CLI. Auto-detects the
# binary in the current folder, keeps a favorites list of MIDI files
# (def not inspired by TegraRcmGUI), and warns you if you tweak a
# setting while a song is already playing, since the running process
# won't pick up the change until it's restarted.
#
# Works on Linux and Windows. Needs tkinter (on Arch: `sudo pacman -S tk`,
# on Debian/Ubuntu: `sudo apt install python3-tk`, on Windows it ships
# with the standard python.org installer already).
 
import glob
import json
import os
import re
import signal
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
 
# flag that checks if you are in the superior or inferior OS (linux or windows)
IS_WINDOWS = os.name == "nt"
 
# gets config or appadata (depending on os) and makes the favourites.json
if IS_WINDOWS:
    CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "steam-haptics-ui")
else:
    CONFIG_DIR = os.path.expanduser("~/.config/steam-haptics-ui")
 
FAVORITES_FILE = os.path.join(CONFIG_DIR, "favorites.json")
 
# checks if windows or linux for .exe or binary
def find_latest_binary():
    candidates = []
    for path in glob.glob("./steam-haptics-singer*"):
        if not os.path.isfile(path):
            continue
        name = os.path.basename(path).lower()
        if not name.startswith("steam-haptics-singer"):
            continue
        candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)
 
 
def load_favorites():
    try:
        with open(FAVORITES_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
 
 
def save_favorites(favorites):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favorites, f, indent=2)
 
 
class SteamHapticsUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Steam Haptics Singer")
        self.geometry("640x680")
        self.minsize(580, 560)
 
        # set application logo
        icon_path = os.path.join(os.path.dirname(__file__), "SteamHapticsLogo.png")
        if os.path.exists(icon_path):
            try:
                self.icon = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, self.icon)
            except Exception:
                pass
 
        self.process = None
        self.reader_thread = None
        self.restart_requested = False
        self.settings_dirty = False  # changed since last (re)start
 
        self.favorites = load_favorites()
 
        # settings panel state
        detected = find_latest_binary()
        # sets if its binary or exe
        default_binary = "./steam-haptics-singer-v1113"
        if IS_WINDOWS:
            default_binary = "steam-haptics-singer-v1113.exe"
        self.binary_path = tk.StringVar(value=detected or default_binary)
        self.midi_path = tk.StringVar(value="")
        self.interval = tk.StringVar(value="10000")
        self.debug_level = tk.IntVar(value=0)
        self.opt_repeat = tk.BooleanVar(value=False)          # -p
        self.opt_gain_from_midi = tk.BooleanVar(value=False)  # -e
        self.opt_two_channel = tk.BooleanVar(value=False)     # -t, SC2026 only
        self.opt_swap_channels = tk.BooleanVar(value=False)   # -s, SC2026 only
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
 
        if detected is None:
            self._log("[no steam-haptics-singer binary found in this folder - set the path manually]\n")
        else:
            self._log(f"[auto-detected binary: {os.path.basename(detected)}]\n")
 
    # ------------------------------------------------------------------ UI (the boring (or interesting) stuff)
 
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}
 
        #  binary + midi path
        file_frame = ttk.LabelFrame(self, text="Files")
        file_frame.pack(fill="x", **pad)
 
        ttk.Label(file_frame, text="Binary:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(file_frame, textvariable=self.binary_path).grid(
            row=0, column=1, sticky="ew", padx=6, pady=4
        )
        ttk.Button(file_frame, text="Browse...", command=self._pick_binary).grid(
            row=0, column=2, padx=3, pady=4
        )
        ttk.Button(file_frame, text="Re-scan", command=self._rescan_binary).grid(
            row=0, column=3, padx=(0, 6), pady=4
        )
 
        ttk.Label(file_frame, text="MIDI file:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(file_frame, textvariable=self.midi_path).grid(
            row=1, column=1, sticky="ew", padx=6, pady=4
        )
        ttk.Button(file_frame, text="Browse...", command=self._pick_midi).grid(
            row=1, column=2, columnspan=2, padx=(3, 6), pady=4, sticky="ew"
        )
        file_frame.columnconfigure(1, weight=1)
 
        #  favorites list
        fav_frame = ttk.LabelFrame(self, text="Favorites")
        fav_frame.pack(fill="x", **pad)
 
        self.fav_listbox = tk.Listbox(fav_frame, height=5, exportselection=False)
        self.fav_listbox.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(6, 3), pady=6)
        self.fav_listbox.bind("<<ListboxSelect>>", self._on_favorite_selected)
        fav_frame.columnconfigure(0, weight=1)
 
        btn_col = ttk.Frame(fav_frame)
        btn_col.grid(row=0, column=1, rowspan=2, sticky="n", padx=(0, 6), pady=6)
        ttk.Button(btn_col, text="＋", width=3, command=self._add_favorite).pack(pady=(0, 4))
        ttk.Button(btn_col, text="🗑", width=3, command=self._remove_favorite).pack()
 
        self._refresh_favorites_list()
 
        #  settings menu
        settings_frame = ttk.LabelFrame(self, text="Settings")
        settings_frame.pack(fill="x", **pad)
 
        ttk.Label(settings_frame, text="Player interval (µs):").grid(
            row=0, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(settings_frame, textvariable=self.interval, width=10).grid(
            row=0, column=1, sticky="w", padx=6, pady=6
        )
        ttk.Label(
            settings_frame,
            text="Lower = better fidelity, more CPU",
            foreground="gray",
        ).grid(row=0, column=2, sticky="w", padx=6, pady=6)
 
        ttk.Label(settings_frame, text="Debug level (0-4):").grid(
            row=1, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Spinbox(
            settings_frame, from_=0, to=4, textvariable=self.debug_level, width=5
        ).grid(row=1, column=1, sticky="w", padx=6, pady=6)
 
        ttk.Checkbutton(
            settings_frame, text="Loop song", variable=self.opt_repeat
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=2)
 
        ttk.Checkbutton(
            settings_frame,
            text="MIDI velocity controls gain",
            variable=self.opt_gain_from_midi,
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=6, pady=2)
 
        ttk.Checkbutton(
            settings_frame,
            text="Limit to two channels (Steam Controller 2026 only)",
            variable=self.opt_two_channel,
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=2)
 
        ttk.Checkbutton(
            settings_frame,
            text="Swap rumble/trackpad channels (Steam Controller 2026 only)",
            variable=self.opt_swap_channels,
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=6, pady=2)
 
        # fires the "restart to apply" warning whenever any of these change
        for var in (
            self.binary_path,
            self.midi_path,
            self.interval,
            self.debug_level,
            self.opt_repeat,
            self.opt_gain_from_midi,
            self.opt_two_channel,
            self.opt_swap_channels,
        ):
            var.trace_add("write", self._on_setting_changed)
 
        #  warning banner (hidden by default)
        self.warning_label = ttk.Label(
            self,
            text="⚠ Settings changed - restart playback for this to take effect",
            foreground="#b35c00",
        )
        # _show_warning() packs it when needed
 
        #  play / stop / restart
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", **pad)
 
        self.play_btn = ttk.Button(control_frame, text="▶ Play", command=self._on_play)
        self.play_btn.pack(side="left", padx=6)
 
        self.stop_btn = ttk.Button(
            control_frame, text="■ Stop", command=self._on_stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=6)
 
        self.restart_btn = ttk.Button(
            control_frame, text="⟳ Restart Playback", command=self._on_restart, state="disabled"
        )
        self.restart_btn.pack(side="left", padx=6)
 
        self.status_label = ttk.Label(control_frame, text="Idle")
        self.status_label.pack(side="left", padx=12)
 
        # command preview
        preview_frame = ttk.LabelFrame(self, text="Command")
        preview_frame.pack(fill="x", **pad)
        self.cmd_preview = tk.StringVar(value="")
        ttk.Label(
            preview_frame, textvariable=self.cmd_preview, foreground="gray", wraplength=600
        ).pack(fill="x", padx=6, pady=6)
        self._update_preview()
 
        #  output log
        log_frame = ttk.LabelFrame(self, text="Output")
        log_frame.pack(fill="both", expand=True, **pad)
 
        self.log_text = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)
 
    # --------------------------------------------------------- binary/midi
 
    def _pick_binary(self):
        path = filedialog.askopenfilename(title="Select steam-haptics-singer binary")
        if path:
            self.binary_path.set(path)
 
    def _rescan_binary(self):
        detected = find_latest_binary()
        if detected:
            self.binary_path.set(detected)
            self._log(f"[re-scanned, using: {detected}]\n")
        else:
            messagebox.showinfo(
                "Not found", "No steam-haptics-singer binary found in this folder."
            )
 
    def _pick_midi(self):
        path = filedialog.askopenfilename(
            title="Select MIDI file", filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")]
        )
        if path:
            self.midi_path.set(path)
 
    # ------------------------------------------------------------ favorites
 
    def _refresh_favorites_list(self):
        self.fav_listbox.delete(0, "end")
        for fav in self.favorites:
            self.fav_listbox.insert("end", fav["name"])
 
    def _on_favorite_selected(self, _event):
        selection = self.fav_listbox.curselection()
        if not selection:
            return
        fav = self.favorites[selection[0]]
        self.midi_path.set(fav["path"])
 
    def _add_favorite(self):
        path = self.midi_path.get().strip()
        if not path:
            messagebox.showwarning("No MIDI file", "Pick a MIDI file first, then add it.")
            return
        if any(fav["path"] == path for fav in self.favorites):
            messagebox.showinfo("Already added", "That MIDI file is already in your favorites.")
            return
        self.favorites.append({"name": os.path.basename(path), "path": path})
        save_favorites(self.favorites)
        self._refresh_favorites_list()
 
    def _remove_favorite(self):
        selection = self.fav_listbox.curselection()
        if not selection:
            return
        del self.favorites[selection[0]]
        save_favorites(self.favorites)
        self._refresh_favorites_list()
 
    # --------------------------------------------------------------- logic (something i don't have)
 
    def _build_args(self):
        args = [self.binary_path.get()]
 
        interval = self.interval.get().strip()
        if interval:
            args += ["-i", interval]
 
        args += ["-d", str(self.debug_level.get())]
 
        if self.opt_repeat.get():
            args.append("-p")
        if self.opt_gain_from_midi.get():
            args.append("-e")
        if self.opt_two_channel.get():
            args.append("-t")
        if self.opt_swap_channels.get():
            args.append("-s")
 
        midi = self.midi_path.get().strip()
        if midi:
            args.append(midi)
 
        return args
 
    def _update_preview(self):
        args = self._build_args()
        self.cmd_preview.set(" ".join(a if a else '""' for a in args))
 
    def _on_setting_changed(self, *_args):
        self._update_preview()
        if self.process is not None:
            self._show_warning()
 
    def _show_warning(self):
        if not self.warning_label.winfo_ismapped():
            self.warning_label.pack(fill="x", padx=10, pady=(0, 4), before=self._first_control_frame())
 
    def _first_control_frame(self):
        # the play/stop/restart row is what the warning should sit just above
        for child in self.winfo_children():
            if isinstance(child, ttk.Frame):
                return child
        return None
 
    def _hide_warning(self):
        if self.warning_label.winfo_ismapped():
            self.warning_label.pack_forget()
 
    def _log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
 
    def _on_play(self):
        if self.process is not None:
            messagebox.showinfo("Already running", "Playback is already running. Stop it first.")
            return
 
        if not self.midi_path.get().strip():
            messagebox.showwarning("No MIDI file", "Please choose a MIDI file first.")
            return
 
        args = self._build_args()
 
        # we give the session a parent so we can politely kill it later
        popen_kwargs = {}
        if IS_WINDOWS:
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            popen_kwargs["start_new_session"] = True
 
        try:
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **popen_kwargs,
            )
        except FileNotFoundError:
            messagebox.showerror(
                "Not found", f"Could not find binary:\n{self.binary_path.get()}"
            )
            self.process = None
            return
        except Exception as e:
            messagebox.showerror("Error starting playback", str(e))
            self.process = None
            return
 
        self._hide_warning()
        self._log(f"\n$ {' '.join(args)}\n")
        self.status_label.config(text="Playing...")
        self.play_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.restart_btn.config(state="normal")
 
        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()
 
    def _read_output(self):
        proc = self.process
        if proc is None or proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                self.after(0, self._log, line)
        except Exception:
            pass
        proc.wait()
        self.after(0, self._on_process_ended)
 
    def _on_process_ended(self):
        code = self.process.returncode if self.process else None
        self._log(f"\n[process ended, exit code {code}]\n")
        self.process = None
        self.status_label.config(text="Idle")
        self.play_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.restart_btn.config(state="disabled")
 
        if self.restart_requested:
            self.restart_requested = False
            self._on_play()
 
    def _on_stop(self):
        if self.process is None:
            return
        self.status_label.config(text="Stopping...")
        try:
            if IS_WINDOWS:
                # forcing to kill the process.
                self.process.terminate()
            else:
                os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
        except Exception as e:
            self._log(f"\n[error stopping process: {e}]\n")
            return
        self.after(200, self._check_stopped)

    def _check_stopped(self):
        if self.process is not None and self.process.poll() is None:
            return
 
    def _on_restart(self):
        if self.process is None:
            return
        self.restart_requested = True
        self.status_label.config(text="Restarting...")
        self._on_stop()
 
    def _on_close(self):
        if self.process is not None and self.process.poll() is None:
            self.restart_requested = False
            self._on_stop()
        self.destroy()
 
 
if __name__ == "__main__":
    app = SteamHapticsUI()
    app.mainloop()
 
