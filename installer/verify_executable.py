from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct


PACKAGE_MAGIC = b"OHPACK2!"
TRAILER_MAGIC = b"OHLNK03!"


def verify(path: Path) -> list[tuple[str, int]]:
    with path.open("rb") as executable:
        executable.seek(-16, 2)
        trailer = executable.read(16)
        if trailer[:8] != TRAILER_MAGIC:
            raise RuntimeError("Missing OverheadLink trailer")
        (package_size,) = struct.unpack("<Q", trailer[8:])
        executable.seek(-16 - package_size, 2)
        package_start = executable.tell()
        if executable.read(8) != PACKAGE_MAGIC:
            raise RuntimeError("Missing OverheadLink package header")
        (file_count,) = struct.unpack("<I", executable.read(4))
        files: list[tuple[str, int]] = []
        for _ in range(file_count):
            path_length, content_length = struct.unpack("<HQ", executable.read(10))
            expected_hash = executable.read(32)
            relative = executable.read(path_length).decode("utf-8")
            digest = hashlib.sha256()
            remaining = content_length
            while remaining:
                chunk = executable.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise RuntimeError(f"Truncated payload file: {relative}")
                digest.update(chunk)
                remaining -= len(chunk)
            if digest.digest() != expected_hash:
                raise RuntimeError(f"Payload hash mismatch: {relative}")
            files.append((relative, content_length))
        if executable.tell() != package_start + package_size:
            raise RuntimeError("Payload size does not match its trailer")
        return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify every file embedded in an OverheadLink Windows executable")
    parser.add_argument("executable", type=Path)
    arguments = parser.parse_args()
    files = verify(arguments.executable.resolve())
    print(f"Verified {len(files)} embedded files")
    for relative, size in files:
        print(f"{size:>10,}  {relative}")


if __name__ == "__main__":
    main()
