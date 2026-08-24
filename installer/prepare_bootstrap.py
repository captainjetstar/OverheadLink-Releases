from __future__ import annotations

from pathlib import Path
import re
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "installer" / "bootstrap.c"
OUTPUT = ROOT / "installer" / "bootstrap_build.c"
PROJECT = ROOT / "pyproject.toml"


def project_version() -> str:
    with PROJECT.open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def build_source(source: str, version: str) -> str:
    # The historical bootstrap had 0.3.6 embedded in several places. Generate
    # those values from pyproject.toml so a future version bump cannot silently
    # ship an installer that considers an older payload current.
    source = re.sub(
        r'#define APP_VERSION L"[0-9]+\.[0-9]+\.[0-9]+"',
        f'#define APP_VERSION L"{version}"\n#define APP_VERSION_A "{version}"',
        source,
        count=1,
    )
    source = re.sub(
        r'return ok && strncmp\(value, "[0-9]+\.[0-9]+\.[0-9]+", [0-9]+\) == 0;',
        'return ok && strncmp(value, APP_VERSION_A, strlen(APP_VERSION_A)) == 0;',
        source,
        count=1,
    )
    source = re.sub(
        r'static const char value\[\] = "[0-9]+\.[0-9]+\.[0-9]+\\r\\n";',
        'static const char value[] = APP_VERSION_A "\\r\\n";',
        source,
        count=1,
    )
    source = re.sub(
        r'OverheadLink-Setup-v[0-9]+\.[0-9]+\.[0-9]+',
        'OverheadLink-Setup',
        source,
        count=1,
    )

    old_copy = '''    if (!paths_equal(self_path, installed_launcher)) {
        CopyFileW(self_path, installed_launcher, FALSE);
    }
    const wchar_t *shortcut_target = file_exists(installed_launcher) ? installed_launcher : self_path;

    BOOL payload_ready = marker_matches(payload_marker)
'''
    new_copy = '''    const BOOL launched_from_external_installer = !paths_equal(self_path, installed_launcher);
    if (launched_from_external_installer) {
        if (!CopyFileW(self_path, installed_launcher, FALSE)) {
            const DWORD copy_error = GetLastError();
            if (copy_error != ERROR_SHARING_VIOLATION && copy_error != ERROR_ACCESS_DENIED) {
                show_error(L"The installed OverheadLink launcher could not be updated.", self_path);
                CloseHandle(setup_mutex);
                return 1;
            }
        }
    }
    const wchar_t *shortcut_target = file_exists(installed_launcher) ? installed_launcher : self_path;

    // An updater executable runs from the Updates folder. Always unpack that
    // payload even if an older installer wrote a stale version marker.
    BOOL payload_ready = !launched_from_external_installer && marker_matches(payload_marker)
'''
    if old_copy not in source:
        raise RuntimeError("bootstrap copy/payload block was not found")
    source = source.replace(old_copy, new_copy, 1)

    required = [
        f'#define APP_VERSION L"{version}"',
        f'#define APP_VERSION_A "{version}"',
        "!launched_from_external_installer && marker_matches(payload_marker)",
        "OverheadLink-Setup",
    ]
    missing = [token for token in required if token not in source]
    if missing:
        raise RuntimeError(f"generated bootstrap is missing: {missing}")
    if "OverheadLink-Setup-v" in source:
        raise RuntimeError("generated bootstrap still contains a versioned setup mutex")
    return source


def main() -> None:
    version = project_version()
    OUTPUT.write_text(build_source(SOURCE.read_text(encoding="utf-8"), version), encoding="utf-8", newline="\n")
    print(f"Generated {OUTPUT.name} for OverheadLink {version}")


if __name__ == "__main__":
    main()
