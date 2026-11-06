"""GitHub Releases uzerinden uygulama ici guncelleme istemcisi."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = "dincer552/RegisterSelecter"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
APP_NAME = "RegisterSelecter"

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class UpdateError(Exception):
    pass


@dataclass
class ReleaseInfo:
    version: tuple[int, int, int]
    tag: str
    download_url: str
    asset_name: str
    size: int


def parse_version(text: str) -> tuple[int, int, int]:
    match = _VERSION_RE.search(text or "")
    if not match:
        raise UpdateError(f"Surdum okunamadi: {text!r}")
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def is_newer(latest: tuple[int, int, int], current: tuple[int, int, int]) -> bool:
    return latest > current


def _headers() -> dict[str, str]:
    return {
        "User-Agent": f"{APP_NAME}-updater",
        "Accept": "application/vnd.github+json",
    }


def check_latest_release(current_version: str, timeout: float = 12.0) -> ReleaseInfo | None:
    """Return ReleaseInfo when GitHub has a newer release, else None."""
    req = urllib.request.Request(LATEST_RELEASE_API, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - network layer errors are opaque by design
        raise UpdateError(f"GitHub'a ulasilamadi: {exc}") from exc

    tag = payload.get("tag_name", "")
    latest_version = parse_version(tag)
    if not is_newer(latest_version, parse_version(current_version)):
        return None

    exe_assets = [
        asset
        for asset in payload.get("assets", [])
        if str(asset.get("name", "")).lower().endswith(".exe")
    ]
    if not exe_assets:
        raise UpdateError(f"{tag} surumunde EXE dosyasi bulunamadi.")
    preferred = next((a for a in exe_assets if APP_NAME.lower() in str(a.get("name", "")).lower()), exe_assets[0])
    return ReleaseInfo(
        version=latest_version,
        tag=tag,
        download_url=preferred["browser_download_url"],
        asset_name=preferred["name"],
        size=int(preferred.get("size", 0)),
    )


def download_release(info: ReleaseInfo, timeout: float = 600.0, progress=None) -> Path:
    """EXE'yi parcacik indirir; progress(indirilen, toplam) ile ilerleme bildirir."""
    dest = Path(tempfile.gettempdir()) / info.asset_name
    req = urllib.request.Request(info.download_url, headers=_headers())
    downloaded = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or 0) or info.size
        with dest.open("wb") as fh:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                downloaded += len(chunk)
                if progress:
                    progress(downloaded, total)
    if not downloaded or downloaded < 1024 * 1024:
        dest.unlink(missing_ok=True)
        raise UpdateError("Indirilen dosya cok kucuk, guncelleme iptal edildi.")
    if total and downloaded != total:
        dest.unlink(missing_ok=True)
        raise UpdateError(f"Indirme yarida kaldi: {downloaded}/{total} bayt.")
    return dest


def apply_and_restart(new_exe: Path) -> None:
    """Indirilen EXE'yi yardimci surec olarak baslatir; swap isi onun isidir.

    Kendi uzerine yazilamadigi icin eski surum swap'i kendisi yapmaz: indirilen
    EXE "--replace-old <eski yol>" ile baslatilir, o da eski EXE serbest kalinca
    kendi kopyasini eski yolun uzerine yazar ve programi eski yoldan acir.
    """
    current = Path(sys.executable)
    if new_exe.resolve() == current.resolve():
        relaunch(current)
        return
    log_swap(f"yardimci surec baslatiliyor: {' '.join(replace_argv(new_exe, current))}")
    subprocess.Popen(replace_argv(new_exe, current), creationflags=_detached_flags(), close_fds=True)


# ---------- EXE degistirme (swap) yardimcilari ----------

REPLACE_FLAG = "--replace-old"
SWAP_TIMEOUT = 120.0
SWAP_INTERVAL = 0.5
SWAP_LOG_NAME = "RegisterSelecter_guncelleme.log"

CREATE_NO_WINDOW = 0x08000000


@dataclass
class SwapOutcome:
    ok: bool
    target: Path
    attempts: int
    error: str = ""
    elapsed: float = 0.0


def _detached_flags() -> int:
    return CREATE_NO_WINDOW if os.name == "nt" else 0


def swap_log_path() -> Path:
    return Path(tempfile.gettempdir()) / SWAP_LOG_NAME


def log_swap(message: str, log_file: Path | None = None) -> None:
    """Swap denemelerini %TEMP% loguna yazar; yazamazsa sessizce gecilir."""
    path = log_file or swap_log_path()
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def parse_replace_target(argv: list[str]) -> Path | None:
    if REPLACE_FLAG not in argv:
        return None
    index = argv.index(REPLACE_FLAG) + 1
    if index >= len(argv):
        return None
    return Path(argv[index])


def replace_argv(new_exe: Path, current: Path) -> list[str]:
    return [str(new_exe), REPLACE_FLAG, str(current)]


def relaunch(exe: Path) -> None:
    subprocess.Popen([str(exe)], creationflags=_detached_flags(), close_fds=True)


def swap_copy(own: Path, target: Path) -> None:
    shutil.copyfile(own, target)


def swap_with_retry(own: Path, target: Path, *, timeout: float = SWAP_TIMEOUT,
                    interval: float = SWAP_INTERVAL, copy=swap_copy,
                    sleep=time.sleep, clock=time.monotonic, note=None) -> SwapOutcome:
    """Kendi EXE'yi hedef yolun uzerine kopyalar; hedef kilitliyse surekli dener.

    Kopyalama ancak eski surum tamamen kapandiginda (veya klasore yazma izni
    oldugunda) basarili olur, bu yuzden basarisizlik tek basine kilitten degil
    izinden de kaynaklanabilir; ayrinti logda okunur.
    """
    started = clock()
    attempts = 0
    error = ""
    while True:
        attempts += 1
        try:
            copy(own, target)
        except OSError as exc:
            error = f"{type(exc).__name__}: {exc}"
            log_swap(f"deneme {attempts} basarisiz: {error}")
            if note:
                note(attempts, error)
        else:
            elapsed = clock() - started
            log_swap(f"swap OK ({attempts} deneme, {elapsed:.1f}s): {own} -> {target}")
            return SwapOutcome(True, target, attempts, "", elapsed)
        if clock() - started >= timeout:
            elapsed = clock() - started
            log_swap(f"swap BASARISIZ ({attempts} deneme, {elapsed:.1f}s): {error}")
            return SwapOutcome(False, target, attempts, error, elapsed)
        sleep(interval)
