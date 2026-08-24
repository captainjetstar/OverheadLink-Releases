from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


REPOSITORY = "captainjetstar/OverheadLink-Releases"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
USER_AGENT = "OverheadLink-Updater"
DOWNLOAD_CHUNK_SIZE = 1024 * 256
ALLOWED_DOWNLOAD_HOSTS = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    version: str
    notes: str
    executable_url: str
    checksum_url: str
    release_url: str


def version_tuple(version: str) -> tuple[int, ...]:
    cleaned = version.strip().lower()
    if cleaned.startswith("v"):
        cleaned = cleaned[1:]
    core = cleaned.split("-", 1)[0].split("+", 1)[0]
    parts = core.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError(f"Unsupported version: {version}")
    values = [int(part) for part in parts]
    while len(values) > 1 and values[-1] == 0:
        values.pop()
    return tuple(values)


def _compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    padded_left = left + (0,) * (width - len(left))
    padded_right = right + (0,) * (width - len(right))
    return (padded_left > padded_right) - (padded_left < padded_right)


def is_newer(candidate: str, installed: str) -> bool:
    return _compare_versions(version_tuple(candidate), version_tuple(installed)) > 0


def _open_url(url: str):
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    return urlopen(request, timeout=30)


def _validate_asset_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in ALLOWED_DOWNLOAD_HOSTS:
        raise RuntimeError("GitHub release contains an unexpected download URL")
    return url


def latest_release() -> UpdateInfo:
    with _open_url(LATEST_RELEASE_API) as response:
        release = json.loads(response.read().decode("utf-8"))
    version = str(release.get("tag_name", "")).lstrip("vV")
    version_tuple(version)
    executable_name = f"OverheadLink_v{version}_Windows_x64.exe"
    checksum_name = f"{executable_name}.sha256"
    assets = {str(asset.get("name")): str(asset.get("browser_download_url")) for asset in release.get("assets", [])}
    executable_url = assets.get(executable_name, "")
    checksum_url = assets.get(checksum_name, "")
    if not executable_url or not checksum_url:
        raise RuntimeError(f"GitHub release v{version} does not contain the verified Windows installer")
    return UpdateInfo(
        version=version,
        notes=str(release.get("body") or "No release notes supplied."),
        executable_url=_validate_asset_url(executable_url),
        checksum_url=_validate_asset_url(checksum_url),
        release_url=str(release.get("html_url") or ""),
    )


def _read_expected_checksum(url: str) -> str:
    with _open_url(_validate_asset_url(url)) as response:
        text = response.read(4096).decode("ascii", errors="strict").strip()
    checksum = text.split()[0].lower() if text else ""
    if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
        raise RuntimeError("The GitHub release checksum is invalid")
    return checksum


def download_update(
    update: UpdateInfo,
    destination_directory: Path | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    expected = _read_expected_checksum(update.checksum_url)
    directory = destination_directory or Path(tempfile.gettempdir()) / "OverheadLink" / "updates"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"OverheadLink_v{update.version}_Windows_x64.exe"
    partial = target.with_suffix(".exe.part")
    digest = hashlib.sha256()
    received = 0
    try:
        with _open_url(_validate_asset_url(update.executable_url)) as response, partial.open("wb") as output:
            total = int(response.headers.get("Content-Length", "0") or 0)
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if progress:
                    progress(received, total)
        if received < 32:
            raise RuntimeError("The downloaded update is unexpectedly small")
        if digest.hexdigest().lower() != expected:
            raise RuntimeError("The downloaded update failed its SHA-256 safety check")
        with partial.open("rb") as executable:
            if executable.read(2) != b"MZ":
                raise RuntimeError("The downloaded update is not a Windows executable")
            if partial.stat().st_size < 16:
                raise RuntimeError("The downloaded update is truncated")
            executable.seek(-16, os.SEEK_END)
            if executable.read(8) != b"OHLNK03!":
                raise RuntimeError("The downloaded update is missing the OverheadLink package signature")
        partial.replace(target)
        return target
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def launch_update(path: Path) -> None:
    if os.name != "nt":
        raise OSError("OverheadLink updates can only be installed automatically on Windows")
    path = path.resolve()
    if not path.is_file() or path.suffix.lower() != ".exe":
        raise OSError("The verified OverheadLink update executable is missing")
    subprocess.Popen([str(path)], cwd=str(path.parent), close_fds=True)
