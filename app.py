import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import base64
import threading
import time
from dataclasses import asdict, dataclass
from typing import Optional

import google.generativeai as genai

import db


@dataclass
class GenerateVideosConfig:
    resolution: str
    duration: int
    fps: Optional[int] = None
    aspect_ratio: Optional[str] = None
    seed: Optional[int] = None
    negative_prompt: Optional[str] = None
    generate_audio: Optional[bool] = None


class VideoApp(tk.Tk):
    """Simple GUI for generating videos using Gemini/Veo."""

    def __init__(self):
        super().__init__()
        self.title("Gemini/Veo Video Generator")

        # API key
        tk.Label(self, text="API Key:").grid(row=0, column=0, sticky="e")
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Combobox(
            self,
            textvariable=self.api_key_var,
            values=db.load_keys(),
            width=40,
        )
        self.api_key_entry.grid(row=0, column=1, pady=5)

        # Prompt
        tk.Label(self, text="Prompt:").grid(row=1, column=0, sticky="ne")
        self.prompt_text = tk.Text(self, height=5, width=40)
        self.prompt_text.grid(row=1, column=1, pady=5)

        # Resolution dropdown
        tk.Label(self, text="Resolution:").grid(row=2, column=0, sticky="e")
        self.resolution_var = tk.StringVar(value="1080p")
        ttk.Combobox(
            self,
            textvariable=self.resolution_var,
            values=["480p", "720p", "1080p"],
            state="readonly",
            width=10,
        ).grid(row=2, column=1, sticky="w")

        # Duration spinbox
        tk.Label(self, text="Duration (s):").grid(row=3, column=0, sticky="e")
        self.duration_var = tk.IntVar(value=10)
        tk.Spinbox(
            self,
            from_=1,
            to=60,
            textvariable=self.duration_var,
            width=5,
        ).grid(row=3, column=1, sticky="w")

        # Container for optional parameters
        advanced = tk.LabelFrame(self, text="Advanced Options")
        advanced.grid(row=4, column=0, columnspan=2, pady=5, sticky="ew")

        # FPS spinbox
        tk.Label(advanced, text="FPS:").grid(row=0, column=0, sticky="e")
        self.fps_var = tk.IntVar(value=24)
        tk.Spinbox(
            advanced,
            from_=1,
            to=120,
            textvariable=self.fps_var,
            width=5,
        ).grid(row=0, column=1, sticky="w")

        # Aspect ratio dropdown
        tk.Label(advanced, text="Aspect Ratio:").grid(
            row=1, column=0, sticky="e"
        )
        self.aspect_ratio_var = tk.StringVar(value="16:9")
        ttk.Combobox(
            advanced,
            textvariable=self.aspect_ratio_var,
            values=["16:9", "9:16"],
            state="readonly",
            width=10,
        ).grid(row=1, column=1, sticky="w")

        # Seed spinbox
        tk.Label(advanced, text="Seed:").grid(row=2, column=0, sticky="e")
        self.seed_var = tk.IntVar(value=0)
        tk.Spinbox(
            advanced,
            from_=0,
            to=2**31 - 1,
            textvariable=self.seed_var,
            width=10,
        ).grid(row=2, column=1, sticky="w")

        # Negative prompt
        tk.Label(advanced, text="Negative Prompt:").grid(
            row=3, column=0, sticky="ne"
        )
        self.negative_prompt_text = tk.Text(advanced, height=2, width=40)
        self.negative_prompt_text.grid(row=3, column=1, pady=5)

        # Generate audio option
        self.generate_audio_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            advanced,
            text="Generate Audio",
            variable=self.generate_audio_var,
        ).grid(row=4, column=1, sticky="w")

        # Generate button
        self.generate_btn = tk.Button(
            self, text="Generate", command=self.generate
        )
        self.generate_btn.grid(row=5, column=0, columnspan=2, pady=10)

        # Progress/result label
        self.status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status_var).grid(
            row=6, column=0, columnspan=2
        )

        # Progress bar used as a spinner while polling
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=200)
        self.progress.grid(row=7, column=0, columnspan=2, pady=5)
        self.progress.grid_remove()

        # Spinner control variables
        self._spinner_running = False

        # Shared context menu for simple text widgets
        self._context_target = None
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="Cut",
            command=lambda: self._context_event("<<Cut>>"),
        )
        self.context_menu.add_command(
            label="Copy",
            command=lambda: self._context_event("<<Copy>>"),
        )
        self.context_menu.add_command(
            label="Paste",
            command=lambda: self._context_event("<<Paste>>"),
        )

        for seq in ("<Button-3>", "<Control-Button-1>"):
            self.api_key_entry.bind(seq, self._show_context_menu, add="+")
            self.prompt_text.bind(seq, self._show_context_menu, add="+")

    def generate(self):
        """Generate the video using the provided prompt and configuration."""
        api_key = self.api_key_var.get().strip()
        db.save_key(api_key)
        self.api_key_entry["values"] = db.load_keys()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not api_key or not prompt:
            messagebox.showerror(
                "Missing Data", "API key and prompt are required."
            )
            return

        self.status_var.set("Generating...")
        self.generate_btn.config(state=tk.DISABLED)
        self.progress.grid()
        self._start_spinner()
        self.update_idletasks()

        threading.Thread(
            target=self._generate_worker,
            args=(api_key, prompt),
            daemon=True,
        ).start()

    def _start_spinner(self) -> None:
        """Start the progress spinner."""
        if not self._spinner_running:
            self._spinner_running = True
            self.progress.configure(mode="indeterminate")
            self.progress['value'] = 0

    def _update_spinner(self) -> None:
        if self._spinner_running:
            try:
                self.progress.step(5)
            except tk.TclError:
                pass

    def _stop_spinner(self) -> None:
        if self._spinner_running:
            self._spinner_running = False
            self.progress.stop()
            self.progress.grid_remove()

    def _context_event(self, sequence: str) -> None:
        if self._context_target is not None:
            self._context_target.event_generate(sequence)

    def _show_context_menu(self, event) -> None:
        self._context_target = event.widget
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _generate_worker(self, api_key: str, prompt: str) -> None:
        """Background thread that performs the API call."""
        genai.configure(api_key=api_key)
        client = genai.GenerativeClient()

        spinner_stop = threading.Event()
        spinner_thread = None
        if hasattr(self, "_update_spinner"):
            def spin_loop():
                while not spinner_stop.is_set():
                    self.after(0, self._update_spinner)
                    time.sleep(0.1)

            spinner_thread = threading.Thread(target=spin_loop, daemon=True)
            spinner_thread.start()

        try:
            negative = self.negative_prompt_text.get("1.0", tk.END).strip()
            cfg = GenerateVideosConfig(
                resolution=self.resolution_var.get(),
                duration=int(self.duration_var.get()),
                fps=int(self.fps_var.get()),
                aspect_ratio=self.aspect_ratio_var.get(),
                seed=int(self.seed_var.get()),
                generate_audio=bool(self.generate_audio_var.get()),
                negative_prompt=negative or None,
            )

            operation = client.models.generate_videos(
                prompt,
                model="models/veo-2.0-generate-001",
                generation_config={
                    k: v
                    for k, v in asdict(cfg).items()
                    if v is not None
                },
            )

            # Poll until the operation completes
            operation.result()

            if getattr(operation, "error", None) is not None:
                # Long running operation completed with an error
                err = getattr(operation.error, "message", str(operation.error))
                self.after(
                    0,
                    lambda err=err: self._handle_error(RuntimeError(err)),
                )
                return

            # Obtain the successful response
            response = operation.result()

            # Extract base64 encoded bytes from the response
            video_bytes = None
            part = response.candidates[0].content.parts[0]
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None and getattr(inline_data, "data", None):
                video_bytes = base64.b64decode(inline_data.data)
            elif getattr(part, "file_data", None) is not None and part.file_data.file_uri:
                # If a file URI is provided, attempt to download the
                # content. Only https is allowed.
                import urllib.request
                import urllib.parse

                uri = part.file_data.file_uri
                scheme = urllib.parse.urlparse(uri).scheme
                if scheme != "https":
                    raise RuntimeError(f"Unsupported URI scheme: {scheme}")
                try:
                    with urllib.request.urlopen(uri) as resp:
                        video_bytes = resp.read()
                except Exception as e:
                    raise RuntimeError(f"Failed to download {uri}") from e

            if video_bytes is None:
                # Fallback to saving the raw response
                video_bytes = bytes(str(response), "utf-8")
            self.after(0, lambda: self._handle_result(video_bytes))
        except Exception as exc:
            # Capture the exception in a default argument so it remains
            # accessible when the scheduled callback executes after the
            # except block has finished.
            self.after(0, lambda exc=exc: self._handle_error(exc))
        finally:
            if spinner_thread is not None:
                spinner_stop.set()
                spinner_thread.join()

    def _handle_result(self, video_bytes: bytes) -> None:
        """Handle saving the generated video on the GUI thread."""
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")],
        )
        if path:
            with open(path, "wb") as f:
                f.write(video_bytes)
            messagebox.showinfo("Saved", f"Video saved to {path}")
        self._stop_spinner()
        self.status_var.set("Done")
        self.generate_btn.config(state=tk.NORMAL)

    def _handle_error(self, exc: Exception) -> None:
        """Display an error message from the GUI thread."""
        self._stop_spinner()
        self.status_var.set("Error generating video")
        messagebox.showerror("Error", str(exc))
        self.generate_btn.config(state=tk.NORMAL)


if __name__ == "__main__":
    app = VideoApp()
    app.mainloop()
