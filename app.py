import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import google.genai as genai
import time
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

        # Duration spinbox
        tk.Label(self, text="Duration (s):").grid(row=2, column=0, sticky="e")
        self.duration_var = tk.IntVar(value=10)
        tk.Spinbox(self, from_=1, to=60, textvariable=self.duration_var, width=5).grid(
            row=2, column=1, sticky="w"
        )

        # Generate button
        self.generate_btn = tk.Button(self, text="Generate", command=self.generate)
        self.generate_btn.grid(row=4, column=0, columnspan=2, pady=10)

        # Progress/result label
        self.status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status_var).grid(row=5, column=0, columnspan=2)

    def generate(self):
        """Generate the video using the provided prompt and configuration."""
        api_key = self.api_key_entry.get().strip()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not api_key or not prompt:
            messagebox.showerror("Missing Data", "API key and prompt are required.")
            return

        self.status_var.set("Generating...")
        self.generate_btn.config(state=tk.DISABLED)
        self.update_idletasks()

        threading.Thread(
            target=self._generate_worker,
            args=(api_key, prompt),
            daemon=True,
        ).start()

    def _generate_worker(self, api_key: str, prompt: str) -> None:
        """Background thread that performs the API call."""
        client = genai.Client(api_key=api_key)
        try:
            operation = client.models.generate_videos(
                model="veo-2.0-generate-001",
                prompt=prompt,
                config=genai.types.GenerateVideosConfig(
                    duration_seconds=int(self.duration_var.get()),
                ),
            )

            while not getattr(operation, "done", True):
                time.sleep(1)
                operation = client.operations.get(operation)

            result = operation.result
            video = result.generated_videos[0].video
            video_bytes = video.video_bytes
            if video_bytes is None and video.uri:
                import urllib.request

                with urllib.request.urlopen(video.uri) as resp:
                    video_bytes = resp.read()
            if video_bytes is None:
                video_bytes = bytes(str(result), "utf-8")
            self.after(0, lambda vb=video_bytes: self._handle_result(vb))
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
        self.status_var.set("Done")
        self.generate_btn.config(state=tk.NORMAL)

    def _handle_error(self, exc: Exception) -> None:
        """Display an error message from the GUI thread."""
        self.status_var.set("Error generating video")
        messagebox.showerror("Error", str(exc))
        self.generate_btn.config(state=tk.NORMAL)


if __name__ == "__main__":
    app = VideoApp()
    app.mainloop()
