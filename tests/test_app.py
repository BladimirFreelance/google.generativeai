import base64
import os
import sys
import types

# Provide a minimal stub for google.generativeai so that app.py can be imported
genai_stub = types.ModuleType("google.generativeai")
genai_stub.configure = lambda api_key: None
genai_stub.GenerativeModel = object
google_pkg = types.ModuleType("google")
google_pkg.__path__ = []
sys.modules.setdefault("google", google_pkg)
sys.modules["google.generativeai"] = genai_stub

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app


class DummyVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class DummyApp:
    def __init__(self):
        self.resolution_var = DummyVar("720p")
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

    class FakeModel:
        def __init__(self, model_id):
            self.model_id = model_id

        def generate_content(self, prompt, generation_config):
            assert generation_config["resolution"] == "720p"
            assert generation_config["duration"] == 5
            assert prompt == "hello"
            data = base64.b64encode(b"video data").decode()
            part = types.SimpleNamespace(
                inline_data=types.SimpleNamespace(data=data),
                file_data=None,
            )
            content = types.SimpleNamespace(parts=[part])
            candidate = types.SimpleNamespace(content=content)
            return types.SimpleNamespace(candidates=[candidate])

    monkeypatch.setattr(app.genai, "configure", fake_configure)
    monkeypatch.setattr(app.genai, "GenerativeModel", lambda model_id: FakeModel(model_id))

    app.VideoApp._generate_worker(dummy, "APIKEY", "hello")

    assert captured_key["key"] == "APIKEY"
    assert dummy.result == b"video data"
    assert dummy.error is None


def test_generate_worker_error(monkeypatch):
    dummy = DummyApp()

    def fake_configure(api_key):
        pass

    class FakeModel:
        def __init__(self, model_id):
            pass

        def generate_content(self, prompt, generation_config):
            raise RuntimeError("boom")

    monkeypatch.setattr(app.genai, "configure", fake_configure)
    monkeypatch.setattr(app.genai, "GenerativeModel", lambda model_id: FakeModel(model_id))

    app.VideoApp._generate_worker(dummy, "KEY", "prompt")

    assert dummy.result is None
    assert isinstance(dummy.error, RuntimeError)
