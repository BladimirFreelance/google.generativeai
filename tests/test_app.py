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
        self.resolution_var = DummyVar("720p")
        self.duration_var = DummyVar(5)
        self.fps_var = DummyVar(30)
        self.aspect_ratio_var = DummyVar("16:9")
        self.seed_var = DummyVar(42)
        self.generate_audio_var = DummyVar(True)
        self.negative_prompt_text = types.SimpleNamespace(
            get=lambda *args, **kwargs: "avoid cats"
        )
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
                assert generation_config["resolution"] == "720p"
                assert generation_config["duration"] == 5
                assert generation_config["fps"] == 30
                assert generation_config["aspect_ratio"] == "16:9"
                assert generation_config["seed"] == 42
                assert generation_config["generate_audio"] is True
                assert generation_config["negative_prompt"] == "avoid cats"
                assert prompt == "hello"
                data = base64.b64encode(b"video data").decode()
                part = types.SimpleNamespace(
                    inline_data=types.SimpleNamespace(data=data),
                    file_data=None,
                )
                content = types.SimpleNamespace(parts=[part])
                candidate = types.SimpleNamespace(content=content)
                result = types.SimpleNamespace(candidates=[candidate])
                return FakeOperation(result_obj=result)

            self.models = types.SimpleNamespace(generate_videos=generate_videos)


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

            self.models = types.SimpleNamespace(generate_videos=generate_videos)

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

            self.models = types.SimpleNamespace(generate_videos=generate_videos)

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
                result = types.SimpleNamespace(candidates=[])
                return FakeOperation(
                    result_obj=result,
                    error=types.SimpleNamespace(message="bad prompt"),
                )

            self.models = types.SimpleNamespace(generate_videos=generate_videos)

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
                result = types.SimpleNamespace(candidates=[])
                return FakeOperation(
                    result_obj=result,
                    error=types.SimpleNamespace(message="delayed bad"),
                )

            self.models = types.SimpleNamespace(generate_videos=generate_videos)

    monkeypatch.setattr(app.genai, "configure", lambda api_key: None)
    monkeypatch.setattr(app.genai, "GenerativeClient", lambda: FakeClient())

    # Run worker; callback is stored but not executed yet
    app.VideoApp._generate_worker(dummy, "KEY", "prompt")

    # Now execute the callback
    dummy._callback()

    assert dummy.result is None
    assert isinstance(dummy.error, RuntimeError)
    assert "delayed bad" in str(dummy.error)
