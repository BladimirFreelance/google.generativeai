import os
import sys
import types

# Provide a minimal stub for google.genai so that app.py can be imported
genai_stub = types.ModuleType("google.genai")

class DummyGenerateVideosConfig:
    def __init__(self, duration_seconds=None):
        self.duration_seconds = duration_seconds

genai_stub.types = types.SimpleNamespace(GenerateVideosConfig=DummyGenerateVideosConfig)
genai_stub.Client = object
google_pkg = types.ModuleType("google")
google_pkg.__path__ = []
sys.modules.setdefault("google", google_pkg)
sys.modules["google.genai"] = genai_stub

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app


class DummyVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


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

    class FakeOperation:
        def __init__(self):
            self.done = True
            self.result = types.SimpleNamespace(
                generated_videos=[
                    types.SimpleNamespace(
                        video=types.SimpleNamespace(video_bytes=b"video data", uri=None)
                    )
                ]
            )

    class FakeClient:
        def __init__(self, api_key):
            captured_key["key"] = api_key
            self.models = self
            self.operations = self

        def generate_videos(self, model, prompt=None, config=None):
            assert model == "veo-2.0-generate-001"
            assert prompt == "hello"
            assert isinstance(config, DummyGenerateVideosConfig)
            assert config.duration_seconds == 5
            return FakeOperation()

        def get(self, operation):
            return operation

    monkeypatch.setattr(app.genai, "Client", FakeClient)

    app.VideoApp._generate_worker(dummy, "APIKEY", "hello")

    assert captured_key["key"] == "APIKEY"
    assert dummy.result == b"video data"
    assert dummy.error is None


def test_generate_worker_error(monkeypatch):
    dummy = DummyApp()

    class FakeClient:
        def __init__(self, api_key):
            pass

        def generate_videos(self, model, prompt=None, config=None):
            raise RuntimeError("boom")

        @property
        def models(self):
            return self

        @property
        def operations(self):
            return self

    monkeypatch.setattr(app.genai, "Client", FakeClient)

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
        def __init__(self, api_key):
            pass

        def generate_videos(self, model, prompt=None, config=None):
            raise RuntimeError("boom")

        @property
        def models(self):
            return self

        @property
        def operations(self):
            return self

    monkeypatch.setattr(app.genai, "Client", FakeClient)

    # Run worker; callback is stored but not executed yet
    app.VideoApp._generate_worker(dummy, "KEY", "prompt")

    # Now execute the callback after the except block has finished
    dummy._callback()

    assert dummy.result is None
    assert isinstance(dummy.error, RuntimeError)
