"""updater.download_release parcacik indirme testlari (ag baglantisi yok)."""

from __future__ import annotations

import io

import pytest

import updater

CHUNK = 64 * 1024


class _FakeResponse:
    def __init__(self, payload: bytes, content_length: int):
        self._buf = io.BytesIO(payload)
        self.headers = {"Content-Length": str(content_length)}

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        return self._buf.read(size)


def _patch_download(monkeypatch, tmp_path, payload: bytes, content_length: int) -> None:
    response = _FakeResponse(payload, content_length)
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *a, **k: response)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))


def _info(size: int) -> updater.ReleaseInfo:
    return updater.ReleaseInfo(
        version=(1, 5, 0),
        tag="v1.5.0",
        download_url="https://example.invalid/RegisterSelecter.exe",
        asset_name="RegisterSelecter.exe",
        size=size,
    )


def test_download_reports_increasing_progress(monkeypatch, tmp_path):
    payload = b"x" * (2 * 1024 * 1024 + 1234)
    _patch_download(monkeypatch, tmp_path, payload, len(payload))
    seen: list[tuple[int, int]] = []
    dest = updater.download_release(_info(len(payload)), progress=lambda d, t: seen.append((d, t)))
    assert dest == tmp_path / "RegisterSelecter.exe"
    assert dest.read_bytes() == payload
    assert len(seen) > len(payload) // CHUNK - 1
    assert [d for d, _t in seen] == sorted(d for d, _t in seen)
    assert seen[-1] == (len(payload), len(payload))


def test_download_detects_truncated_file(monkeypatch, tmp_path):
    payload = b"y" * (3 * 1024 * 1024)
    _patch_download(monkeypatch, tmp_path, payload, len(payload) + CHUNK)
    with pytest.raises(updater.UpdateError, match="yarida kaldi"):
        updater.download_release(_info(size=0))
    assert not (tmp_path / "RegisterSelecter.exe").exists()


def test_download_rejects_tiny_file(monkeypatch, tmp_path):
    _patch_download(monkeypatch, tmp_path, b"z" * 512, 512)
    with pytest.raises(updater.UpdateError, match="cok kucuk"):
        updater.download_release(_info(size=512))
    assert not (tmp_path / "RegisterSelecter.exe").exists()
