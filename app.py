import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import google.generativeai as genai
import base64
import threading


class VideoApp(tk.Tk):
    """Simple GUI for generating videos using Gemini/Veo."""

    def __init__(self):
        super().__init__()
        self.title("Gemini/Veo Video Generator")

        # API key
        tk.Label(self, text="API Key:").grid(row=0, column=0, sticky="e")
        self.api_key_entry = tk.Entry(self, width=40, show="*")
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
        tk.Spinbox(self, from_=1, to=60, textvariable=self.duration_var, width=5).grid(
            row=3, column=1, sticky="w"
        )

        # Generate button
        self.generate_btn = tk.Button(self, text="Generate", command=self.generate)
        self.generate_btn.grid(row=4, column=0, columnspan=2, pady=10)

        # Progress/result label
        self.status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status_var).grid(row=5, column=0, columnspan=2)

        # Progress bar used as a spinner while polling
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=200)
        self.progress.grid(row=6, column=0, columnspan=2, pady=5)
        self.progress.grid_remove()
        
        # Spinner control variables
        self._spinner_running = False

    def generate(self):
        """Generate the video using the provided prompt and configuration."""
        api_key = self.api_key_entry.get().strip()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not api_key or not prompt:
            messagebox.showerror("Missing Data", "API key and prompt are required.")
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
            self.progress.start(10)
            self.after(100, self._update_spinner)

    def _update_spinner(self) -> None:
        if self._spinner_running:
            self.progress.step(5)
            self.after(100, self._update_spinner)

    def _stop_spinner(self) -> None:
        if self._spinner_running:
            self._spinner_running = False
            self.progress.stop()
            self.progress.grid_remove()

    def _generate_worker(self, api_key: str, prompt: str) -> None:
        """Background thread that performs the API call."""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/veo-2.0-generate-001")
        try:
            operation = model.generate_content(
                prompt,
                generation_config={
                    "resolution": self.resolution_var.get(),
                    "duration": int(self.duration_var.get()),
                },
            )

            # Poll until the operation completes and obtain the response
            response = operation.result()

            if getattr(operation, "error", None) is not None:
                # Long running operation completed with an error
                err = getattr(operation.error, "message", str(operation.error))
                raise RuntimeError(err)

            # Extract base64 encoded bytes from the response
            video_bytes = None
            try:
                part = response.candidates[0].content.parts[0]
                if hasattr(part, "inline_data") and part.inline_data.data:
                    video_bytes = base64.b64decode(part.inline_data.data)
                elif hasattr(part, "file_data") and part.file_data.file_uri:
                    # If a file URI is provided, attempt to download the content
                    import urllib.request

                    with urllib.request.urlopen(part.file_data.file_uri) as resp:
                        video_bytes = resp.read()
            except Exception:
                pass

            if video_bytes is None:
                # Fallback to saving the raw response
                video_bytes = bytes(str(response), "utf-8")
            self.after(0, lambda: self._handle_result(video_bytes))
        except Exception as exc:
            # Capture the exception in a default argument so it remains
            # accessible when the scheduled callback executes after the
            # except block has finished.
            self.after(0, lambda exc=exc: self._handle_error(exc))

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
