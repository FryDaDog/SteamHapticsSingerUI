#!/usr/bin/env python3
# steam_haptics_ui.py
#
# Little GUI wrapper around the steam-haptics-singer CLI so you don't
# have to remember all the flags every time. Point it at the binary
# and a MIDI file, flip the settings you want, hit play.
#
# Stop actually sends SIGINT to the process group - same thing that
# happens when you hit Ctrl+C in a terminal - instead of just killing
# it, since the tool probably wants to clean up the USB handle on the
# way out.
#
# Linux only. Needs tkinter (usually `sudo apt install python3-tk` if
# it's not already there).

import os
import signal
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class SteamHapticsUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Steam Haptics Singer")
        self.geometry("620x560")
        self.minsize(560, 480)

        self.process = None
        self.reader_thread = None

        # everything the settings panel controls
        self.binary_path = tk.StringVar(value="./steam-haptics-singer-v1113")
        self.midi_path = tk.StringVar(value="")
        self.interval = tk.StringVar(value="10000")
        self.debug_level = tk.IntVar(value=0)
        self.opt_repeat = tk.BooleanVar(value=False)          # -p
        self.opt_gain_from_midi = tk.BooleanVar(value=False)  # -e
        self.opt_two_channel = tk.BooleanVar(value=False)     # -t, 2026 controller only
        self.opt_swap_channels = tk.BooleanVar(value=False)   # -s, 2026 controller only

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # binary + midi pickers up top
        file_frame = ttk.LabelFrame(self, text="Files")
        file_frame.pack(fill="x", **pad)

        ttk.Label(file_frame, text="Binary:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(file_frame, textvariable=self.binary_path).grid(
            row=0, column=1, sticky="ew", padx=6, pady=4
        )
        ttk.Button(file_frame, text="Browse...", command=self._pick_binary).grid(
            row=0, column=2, padx=6, pady=4
        )

        ttk.Label(file_frame, text="MIDI file:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(file_frame, textvariable=self.midi_path).grid(
            row=1, column=1, sticky="ew", padx=6, pady=4
        )
        ttk.Button(file_frame, text="Browse...", command=self._pick_midi).grid(
            row=1, column=2, padx=6, pady=4
        )
        file_frame.columnconfigure(1, weight=1)

        # the actual settings menu - maps straight onto the CLI flags
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
            text="Lower = better fidelity, more CPU. 10000 is the default.",
            foreground="gray",
        ).grid(row=0, column=2, sticky="w", padx=6, pady=6)

        ttk.Label(settings_frame, text="Debug level (0-4):").grid(
            row=1, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Spinbox(
            settings_frame, from_=0, to=4, textvariable=self.debug_level, width=5
        ).grid(row=1, column=1, sticky="w", padx=6, pady=6)

        ttk.Checkbutton(
            settings_frame, text="Repeat song (-p)", variable=self.opt_repeat
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=2)

        ttk.Checkbutton(
            settings_frame,
            text="MIDI velocity controls gain (-e)",
            variable=self.opt_gain_from_midi,
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=6, pady=2)

        ttk.Checkbutton(
            settings_frame,
            text="Limit to two channels (-t, Steam Controller 2026 only)",
            variable=self.opt_two_channel,
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=6, pady=2)

        ttk.Checkbutton(
            settings_frame,
            text="Swap rumble/trackpad channels (-s, Steam Controller 2026 only)",
            variable=self.opt_swap_channels,
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=6, pady=2)

        # play / stop
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", **pad)

        self.play_btn = ttk.Button(control_frame, text="▶ Play", command=self._on_play)
        self.play_btn.pack(side="left", padx=6)

        self.stop_btn = ttk.Button(
            control_frame, text="■ Stop (Ctrl+C)", command=self._on_stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=6)

        self.status_label = ttk.Label(control_frame, text="Idle")
        self.status_label.pack(side="left", padx=12)

        # show the command we're about to run, mostly so you can double check it
        preview_frame = ttk.LabelFrame(self, text="Command")
        preview_frame.pack(fill="x", **pad)
        self.cmd_preview = tk.StringVar(value="")
        ttk.Label(
            preview_frame, textvariable=self.cmd_preview, foreground="gray", wraplength=580
        ).pack(fill="x", padx=6, pady=6)

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
            var.trace_add("write", lambda *_: self._update_preview())
        self._update_preview()

        # raw stdout/stderr from the tool
        log_frame = ttk.LabelFrame(self, text="Output")
        log_frame.pack(fill="both", expand=True, **pad)

        self.log_text = tk.Text(log_frame, height=12, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

    # --------------------------------------------------------------- logic

    def _pick_binary(self):
        path = filedialog.askopenfilename(title="Select steam-haptics-singer binary")
        if path:
            self.binary_path.set(path)

    def _pick_midi(self):
        path = filedialog.askopenfilename(
            title="Select MIDI file", filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")]
        )
        if path:
            self.midi_path.set(path)

    def _build_args(self):
        # turns the current settings into the actual argv list
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

        try:
            # start_new_session puts the child in its own process group,
            # so Stop can signal just this process (and anything it spawns)
            # without touching the GUI itself
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
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

        self._log(f"\n$ {' '.join(args)}\n")
        self.status_label.config(text="Playing...")
        self.play_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()

    def _read_output(self):
        # runs in a background thread, just pipes stdout into the log box
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

    def _on_stop(self):
        if self.process is None:
            return
        self.status_label.config(text="Stopping (Ctrl+C sent)...")
        try:
            # SIGINT to the whole group - this is exactly what you'd get
            # from Ctrl+C in a terminal, so the tool can shut down cleanly
            os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
        except Exception as e:
            self._log(f"\n[error sending Ctrl+C: {e}]\n")
            return

        # give it a few seconds to exit on its own before offering to force it
        self.after(3000, self._check_stopped)

    def _check_stopped(self):
        if self.process is not None and self.process.poll() is None:
            if messagebox.askyesno(
                "Still running",
                "The process didn't exit after Ctrl+C. Force kill it?",
            ):
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except Exception as e:
                    self._log(f"\n[error force-killing: {e}]\n")

    def _on_close(self):
        if self.process is not None and self.process.poll() is None:
            self._on_stop()
        self.destroy()


if __name__ == "__main__":
    app = SteamHapticsUI()
    app.mainloop()
