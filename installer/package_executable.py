from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import struct


PACKAGE_MAGIC = b"OHPACK2!"
TRAILER_MAGIC = b"OHLNK03!"


def payload_files(project: Path) -> list[Path]:
    patterns = (
        "run_overheadlink.py",
        "README.md",
        "QUICK_START.md",
        "PIN_ASSIGNMENTS.md",
        "RELEASE_NOTES.md",
        "requirements.txt",
        "pyproject.toml",
        "src/**/*.py",
        ".github/workflows/*.yml",
        "profiles/*.json",
        "firmware/**/*.ino",
        "vendor/python-3.12.10-amd64.exe",
        "vendor/pyserial-3.5-py2.py3-none-any.whl",
        "vendor/SimConnect.dll",
    )
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in project.glob(pattern) if path.is_file())
    return sorted(files, key=lambda path: path.relative_to(project).as_posix().casefold())


def build(base_executable: Path, project: Path, output: Path) -> None:
    files = payload_files(project)
    if not files:
        raise RuntimeError("No payload files were found")
    required = {
        "run_overheadlink.py",
        "profiles/a320_fenix_overhead.json",
        "vendor/python-3.12.10-amd64.exe",
        "vendor/pyserial-3.5-py2.py3-none-any.whl",
        "vendor/SimConnect.dll",
    }
    available = {path.relative_to(project).as_posix() for path in files}
    missing = required - available
    if missing:
        raise RuntimeError(f"Missing required payload files: {sorted(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with base_executable.open("rb") as source, output.open("wb") as target:
        shutil.copyfileobj(source, target, 1024 * 1024)
        package_start = target.tell()
        target.write(PACKAGE_MAGIC)
        target.write(struct.pack("<I", len(files)))
        for path in files:
            relative = path.relative_to(project).as_posix().encode("utf-8")
            if len(relative) > 2048:
                raise RuntimeError(f"Payload path is too long: {path}")
            digest = hashlib.sha256()
            with path.open("rb") as payload:
                for chunk in iter(lambda: payload.read(1024 * 1024), b""):
                    digest.update(chunk)
            target.write(struct.pack("<HQ", len(relative), path.stat().st_size))
            target.write(digest.digest())
            target.write(relative)
            with path.open("rb") as payload:
                shutil.copyfileobj(payload, target, 1024 * 1024)
        package_size = target.tell() - package_start
        target.write(TRAILER_MAGIC)
        target.write(struct.pack("<Q", package_size))

    print(f"Built {output} with {len(files)} payload files ({output.stat().st_size:,} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append the verified OverheadLink payload to the native Windows launcher")
    parser.add_argument("base_executable", type=Path)
    parser.add_argument("project", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    build(arguments.base_executable.resolve(), arguments.project.resolve(), arguments.output.resolve())


if __name__ == "__main__":
    main()
