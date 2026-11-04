"""GitHub Releases uzerinden uygulama ici guncelleme istemcisi."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
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
    """Swap the running EXE with the downloaded one and relaunch it."""
    current = Path(sys.executable)
    pid = os.getpid()
    ps_script = f"""
$ErrorActionPreference = "Stop"
$exe = "{current}"
$new = "{new_exe}"
while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 400 }}
do {{
    try {{ Move-Item -Force -Path $new -Destination $exe; break }}
    catch {{ Start-Sleep -Milliseconds 500 }}
}} while ($true)
Start-Process -FilePath $exe
"""
    script = Path(tempfile.gettempdir()) / "RegisterSelecter_update.ps1"
    script.write_text(ps_script, encoding="utf-8")
    detached = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NO_WINDOW
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        creationflags=detached,
        close_fds=True,
    )
