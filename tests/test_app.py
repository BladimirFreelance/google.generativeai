import base64
import os
import sys
import types

# Provide a minimal stub for google.generativeai so that app.py can be imported
genai_stub = types.ModuleType("google.generativeai")
genai_stub.configure = lambda api_key: None
genai_stub.GenerativeClient = object
google_pkg = types.ModuleType("google")
google_pkg.__path__ = []
sys.modules.setdefault("google", google_pkg)
sys.modules["google.generativeai"] = genai_stub

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

import app  # noqa: E402


class DummyVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class FakeOperation:
    def __init__(self, result_obj=None, error=None, raise_on_result=False):
        self._result_obj = result_obj
        self.error = error
        self._raise_on_result = raise_on_result

    def result(self):
        if self._raise_on_result:
            raise RuntimeError("poll error")
        return self._result_obj


class DummyApp:
    def __init__(self):
        self.duration_var = DummyVar(5)
        self.result = None
        self.error = None

    def after(self, delay, func):
        func()

    def _handle_result(self, data):
        self.result = data

    def _handle_error(self, exc):
        self.error = exc


def test_generate_worker_success(monkeypatch):
    dummy = DummyApp()
    captured_key = {}

    def fake_configure(api_key):
        captured_key["key"] = api_key

    class FakeClient:
        def __init__(self):
            def generate_videos(prompt, *, model, generation_config):
                assert model == "models/veo-2.0-generate-001"
                assert generation_config["duration"] == 5
                assert prompt == "hello"
                data = base64.b64encode(b"video data").decode()
                part = types.SimpleNamespace(
                    inline_data=types.SimpleNamespace(data=data),
                    file_data=None,
                )
                content = types.SimpleNamespace(parts=[part])
                candidate = types.SimpleNamespace(content=content)
                result = types.SimpleNamespace(
                    candidates=[candidate]
                )
                return FakeOperation(result_obj=result)

            self.models = types.SimpleNamespace(
                generate_videos=generate_videos
            )

    monkeypatch.setattr(app.genai, "configure", fake_configure)
    monkeypatch.setattr(app.genai, "GenerativeClient", lambda: FakeClient())

    app.VideoApp._generate_worker(dummy, "APIKEY", "hello")

    assert captured_key["key"] == "APIKEY"
    assert dummy.result == b"video data"
    assert dummy.error is None


def test_generate_worker_error(monkeypatch):
    dummy = DummyApp()

    def fake_configure(api_key):
        pass

    class FakeClient:
        def __init__(self):
            def generate_videos(prompt, *, model, generation_config):
                return FakeOperation(raise_on_result=True)

            self.models = types.SimpleNamespace(
                generate_videos=generate_videos
            )

    monkeypatch.setattr(app.genai, "configure", fake_configure)
    monkeypatch.setattr(app.genai, "GenerativeClient", lambda: FakeClient())

    app.VideoApp._generate_worker(dummy, "KEY", "prompt")

    assert dummy.result is None
    assert isinstance(dummy.error, RuntimeError)


class DelayedDummyApp(DummyApp):
    def __init__(self):
        super().__init__()
        self._callback = None

    def after(self, delay, func):
        self._callback = func


def test_generate_worker_error_delayed(monkeypatch):
    dummy = DelayedDummyApp()

    class FakeClient:
        def __init__(self):
            def generate_videos(prompt, *, model, generation_config):
                return FakeOperation(raise_on_result=True)

            self.models = types.SimpleNamespace(
                generate_videos=generate_videos
            )

    monkeypatch.setattr(app.genai, "configure", lambda api_key: None)
    monkeypatch.setattr(app.genai, "GenerativeClient", lambda: FakeClient())

    # Run worker; callback is stored but not executed yet
    app.VideoApp._generate_worker(dummy, "KEY", "prompt")

    # Now execute the callback after the except block has finished
    dummy._callback()

    assert dummy.result is None
    assert isinstance(dummy.error, RuntimeError)


def test_generate_worker_operation_error(monkeypatch):
    dummy = DummyApp()

    class FakeClient:
        def __init__(self):
            def generate_videos(prompt, *, model, generation_config):
                result = types.SimpleNamespace(
                    candidates=[]
                )
                return FakeOperation(
                    result_obj=result,
                    error=types.SimpleNamespace(message="bad prompt"),
                )

            self.models = types.SimpleNamespace(
                generate_videos=generate_videos
            )

    monkeypatch.setattr(app.genai, "configure", lambda api_key: None)
    monkeypatch.setattr(app.genai, "GenerativeClient", lambda: FakeClient())

    app.VideoApp._generate_worker(dummy, "KEY", "prompt")

    assert dummy.result is None
    assert isinstance(dummy.error, RuntimeError)
    assert "bad prompt" in str(dummy.error)


def test_generate_worker_operation_error_delayed(monkeypatch):
    dummy = DelayedDummyApp()

    class FakeClient:
        def __init__(self):
            def generate_videos(prompt, *, model, generation_config):
                result = types.SimpleNamespace(
                    candidates=[]
                )
                return FakeOperation(
                    result_obj=result,
                    error=types.SimpleNamespace(message="delayed bad"),
                )

            self.models = types.SimpleNamespace(
                generate_videos=generate_videos
            )

    monkeypatch.setattr(app.genai, "configure", lambda api_key: None)
    monkeypatch.setattr(app.genai, "GenerativeClient", lambda: FakeClient())

    # Run worker; callback is stored but not executed yet
    app.VideoApp._generate_worker(dummy, "KEY", "prompt")

    # Now execute the callback
    dummy._callback()

    assert dummy.result is None
    assert isinstance(dummy.error, RuntimeError)
    assert "delayed bad" in str(dummy.error)


def test_context_menu_bindings(monkeypatch):
    """Ensure right-click bindings exist for text widgets."""
    tk_stub = types.ModuleType("tkinter")

    class DummyVar:
        def __init__(self, value=None):
            self.value = value

        def get(self):
            return self.value

    class DummyWidget:
        def __init__(self, *a, **k):
            self.bindings = {}

        def grid(self, *a, **k):
            pass

        def grid_remove(self, *a, **k):
            pass

        def configure(self, *a, **k):
            pass

        config = configure

        def bind(self, seq=None, func=None, add=None):
            if func is not None:
                self.bindings[seq] = func
            return self.bindings.get(seq)

        def event_generate(self, *a, **k):
            pass

    class DummyMenu(DummyWidget):
        def add_command(self, *a, **k):
            pass

        def tk_popup(self, *a, **k):
            pass

        def grab_release(self):
            pass

    class DummyTk(DummyWidget):
        def title(self, *a, **k):
            pass

        def update_idletasks(self, *a, **k):
            pass

        def after(self, delay, func):
            func()

    tk_stub.Tk = DummyTk
    tk_stub.Label = DummyWidget
    tk_stub.Entry = DummyWidget
    tk_stub.Text = DummyWidget
    tk_stub.LabelFrame = DummyWidget
    tk_stub.Spinbox = DummyWidget
    tk_stub.Checkbutton = DummyWidget
    tk_stub.Button = DummyWidget
    tk_stub.StringVar = lambda *a, value=None, **k: DummyVar(value)
    tk_stub.IntVar = lambda *a, value=None, **k: DummyVar(value)
    tk_stub.BooleanVar = lambda *a, value=None, **k: DummyVar(value)
    tk_stub.Menu = DummyMenu
    tk_stub.END = "end"

    ttk_stub = types.ModuleType("tkinter.ttk")
    ttk_stub.Combobox = DummyWidget
    ttk_stub.Progressbar = DummyWidget

    filedialog_stub = types.ModuleType("tkinter.filedialog")
    filedialog_stub.asksaveasfilename = lambda *a, **k: ""

    messagebox_stub = types.ModuleType("tkinter.messagebox")
    messagebox_stub.showerror = lambda *a, **k: None
    messagebox_stub.showinfo = lambda *a, **k: None

    monkeypatch.setitem(sys.modules, "tkinter", tk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", ttk_stub)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", filedialog_stub)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", messagebox_stub)

    import importlib

    importlib.reload(app)

    gui = app.VideoApp()

    for seq in ("<Button-3>", "<Control-Button-1>"):
        assert gui.api_key_entry.bind(seq) is not None
        assert gui.prompt_text.bind(seq) is not None


def test_generate_worker_fetch_error(monkeypatch):
    dummy = DummyApp()

    class FakeClient:
        def __init__(self):
            def generate_videos(prompt, *, model, generation_config):
                part = types.SimpleNamespace(
                    inline_data=types.SimpleNamespace(data="bad"),
                    file_data=None,
                )
                content = types.SimpleNamespace(parts=[part])
                candidate = types.SimpleNamespace(content=content)
                result = types.SimpleNamespace(candidates=[candidate])
                return FakeOperation(result_obj=result)

            self.models = types.SimpleNamespace(
                generate_videos=generate_videos
            )

    monkeypatch.setattr(app.genai, "configure", lambda api_key: None)
    monkeypatch.setattr(app.genai, "GenerativeClient", lambda: FakeClient())

    app.VideoApp._generate_worker(dummy, "KEY", "prompt")

    assert dummy.result is None
    assert isinstance(dummy.error, Exception)
