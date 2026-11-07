import subprocess
import sys

from fastapi.testclient import TestClient

import app.main as main_module


def test_importing_app_main_emits_no_on_event_deprecation_warning():
    code = (
        "import warnings\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    warnings.simplefilter('always')\n"
        "    import app.main\n"
        "bad = [str(w.message) for w in caught if 'on_event' in str(w.message)]\n"
        "assert not bad, bad\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_lifespan_runs_startup_and_shutdown(monkeypatch):
    calls: list[str] = []

    class FakeSession:
        def close(self) -> None:
            calls.append("close")

    async def fake_loop() -> None:
        calls.append("loop-started")
        try:
            await __import__("asyncio").sleep(3600)
        except BaseException:
            calls.append("loop-cancelled")
            raise

    monkeypatch.setattr(main_module, "SessionLocal", FakeSession)
    monkeypatch.setattr(main_module, "ensure_secret_state", lambda db: calls.append("ensure"))
    monkeypatch.setattr(main_module, "maybe_rotate_secrets", lambda db: calls.append("rotate"))
    monkeypatch.setattr(main_module, "_rotation_loop", fake_loop)

    with TestClient(main_module.app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert main_module.rotation_task is not None
        assert calls[:3] == ["ensure", "rotate", "close"]

    assert main_module.rotation_task is None
    assert "loop-cancelled" in calls
