"""updater.download_release parcacik indirme ve EXE swap testleri (ag baglantisi yok)."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

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


# ---------- EXE swap (yeniden baslatma) ----------


class _FakeClock:
    """sleep() her cagrildiginda saati interval kadar ilerletir."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _locked_copy(failures: int, written: list[Path]):
    """Ilk `failures` denemede hedefi kilitli gibi PermissionError ile reddet."""

    def copy(own, target):
        if len(written) < failures:
            written.append(Path(target))
            raise PermissionError(13, "The process cannot access the file because it is being used")
        Path(target).write_bytes(Path(own).read_bytes())
        written.append(Path(target))

    return copy


def test_parse_replace_target_reads_path():
    assert updater.parse_replace_target(["RegisterSelecter.exe", "--replace-old", r"C:\a\RegisterSelecter.exe"]) == Path(
        r"C:\a\RegisterSelecter.exe"
    )
    assert updater.parse_replace_target(["RegisterSelecter.exe"]) is None
    assert updater.parse_replace_target(["RegisterSelecter.exe", "--replace-old"]) is None


def test_replace_argv_roundtrip():
    argv = updater.replace_argv(Path(r"C:\t\RegisterSelecter.exe"), Path(r"C:\d\RegisterSelecter.exe"))
    assert argv == [r"C:\t\RegisterSelecter.exe", updater.REPLACE_FLAG, r"C:\d\RegisterSelecter.exe"]
    assert updater.parse_replace_target(argv) == Path(r"C:\d\RegisterSelecter.exe")


def test_swap_retries_until_target_is_free(tmp_path):
    own = tmp_path / "yeni.exe"
    own.write_bytes(b"NEW")
    target = tmp_path / "eski.exe"
    target.write_bytes(b"OLD")
    clock = _FakeClock()
    written: list[Path] = []
    notes: list[tuple[int, str]] = []

    outcome = updater.swap_with_retry(
        own,
        target,
        timeout=10.0,
        interval=1.0,
        copy=_locked_copy(2, written),
        sleep=clock.sleep,
        clock=clock.clock,
        note=lambda attempt, error: notes.append((attempt, error)),
    )
    assert outcome.ok and outcome.attempts == 3 and outcome.elapsed == 2.0
    assert outcome.error == ""
    assert len(notes) == 2 and all("PermissionError" in e for _a, e in notes)
    assert target.read_bytes() == b"NEW"


def test_swap_gives_up_at_timeout(tmp_path):
    own = tmp_path / "yeni.exe"
    own.write_bytes(b"NEW")
    missing_dir_target = tmp_path / "yok" / "RegisterSelecter.exe"
    clock = _FakeClock()
    seen: list[int] = []

    outcome = updater.swap_with_retry(
        own,
        missing_dir_target,
        timeout=3.0,
        interval=1.0,
        sleep=clock.sleep,
        clock=clock.clock,
        note=lambda attempt, _e: seen.append(attempt),
    )
    assert outcome.ok is False
    assert outcome.error.startswith("FileNotFoundError")
    assert outcome.attempts == 4, "timeout'a kadar 1 + 3 tekrar denemesi"
    assert seen == [1, 2, 3, 4]
    assert not missing_dir_target.exists()


def test_swap_copy_replaces_content_in_place(tmp_path):
    own = tmp_path / "yeni.exe"
    own.write_bytes(b"NEW")
    target = tmp_path / "eski.exe"
    target.write_bytes(b"OLDLONGER")

    updater.swap_copy(own, target)

    assert target.read_bytes() == b"NEW"
    assert own.exists(), "kendi EXE'si hedefe tasinmaz, kopyalanir"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows dosya kilidi davranisi")
def test_swap_real_windows_lock_blocks_then_succeeds(tmp_path):
    """Eski EXE calisirken hedef kilitlidir; kilid acilir acilmaz swap olur."""
    import msvcrt

    own = tmp_path / "yeni.exe"
    own.write_bytes(b"NEW" * 4096)
    target = tmp_path / "eski.exe"
    target.write_bytes(b"OLD")

    handle = os.open(target, os.O_RDWR)
    clock = _FakeClock()
    notes: list[int] = []
    try:
        msvcrt.locking(handle, msvcrt.LK_NBLCK, 4096)

        def unlock_after_first_attempt(attempt: int, error: str) -> None:
            notes.append(attempt)
            msvcrt.locking(handle, msvcrt.LK_UNLCK, 4096)

        outcome = updater.swap_with_retry(
            own, target, timeout=10.0, interval=1.0,
            sleep=clock.sleep, clock=clock.clock, note=unlock_after_first_attempt,
        )
    finally:
        os.close(handle)

    assert outcome.ok is True and outcome.attempts == 2, (outcome, notes)
    assert notes == [1]
    assert outcome.error == ""
    assert target.read_bytes() == own.read_bytes()


def test_swap_log_append_and_failure_is_silent(tmp_path):
    log = tmp_path / "guncelleme.log"
    updater.log_swap("ilk satir", log_file=log)
    updater.log_swap("ikinci satir", log_file=log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and lines[0].endswith("ilk satir")
    assert lines[1].split(" ", 2)[2] == "ikinci satir"

    updater.log_swap("yazilamaz", log_file=tmp_path / "yok" / "a.log")  # hata fırlatmamalı


def test_apply_and_restart_launches_helper(monkeypatch, tmp_path):
    started: list[list[str]] = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda argv, **k: started.append(list(argv)))
    current = tmp_path / "RegisterSelecter.exe"
    new = tmp_path / "indirilen" / "RegisterSelecter.exe"
    new.parent.mkdir()
    new.write_bytes(b"NEW")
    monkeypatch.setattr(updater.sys, "executable", str(current))

    updater.apply_and_restart(new)

    assert started == [[str(new), updater.REPLACE_FLAG, str(current)]]
    assert "powershell.exe" not in started[0][0].lower()


def test_apply_and_restart_skips_swap_for_same_file(monkeypatch, tmp_path):
    started: list[list[str]] = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda argv, **k: started.append(list(argv)))
    current = tmp_path / "RegisterSelecter.exe"
    monkeypatch.setattr(updater.sys, "executable", str(current))

    updater.apply_and_restart(current)

    assert started == [[str(current)]]
