"""Tests for the Ryu probe CLI helper."""

from src.controller import ryu_probe


def test_probe_ryu_returns_switch_list(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b"[1, 2, 3]"

    monkeypatch.setattr(ryu_probe, "urlopen", lambda *args, **kwargs: FakeResponse())

    switches = ryu_probe.probe_ryu("http://127.0.0.1:8080")
    assert switches == [1, 2, 3]
