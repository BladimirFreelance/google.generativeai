import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import base64
import threading
import time

import google.generativeai as genai
import db


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
        model = genai.GenerativeModel("models/veo-2.0-generate-001")

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
            operation = model.generate_content(prompt)

            response = operation.result()
            if getattr(operation, "error", None) is not None:
                # Long running operation completed with an error
                err = getattr(operation.error, "message", str(operation.error))
                self.after(
                    0,
                    lambda err=err: self._handle_error(RuntimeError(err)),
                )
                return

            # Obtain the successful response (already stored in 'response')

            # Extract base64 encoded bytes from the response
            video_bytes = None
            try:
                part = response.candidates[0].content.parts[0]
                if hasattr(part, "inline_data") and part.inline_data.data:
                    video_bytes = base64.b64decode(part.inline_data.data)
                else:
                    has_file_data = (
                        getattr(part, "file_data", None) is not None
                    )
                    if has_file_data and part.file_data.file_uri:
                        # If a file URI is provided, attempt to download the
                        # content
                        import urllib.request

                        with urllib.request.urlopen(
                            part.file_data.file_uri
                        ) as resp:
                            video_bytes = resp.read()
            except Exception as exc:
                self.after(0, lambda exc=exc: self._handle_error(exc))
                return

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
