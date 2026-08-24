from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import time
import tomllib
import unittest


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from overheadlink import __version__
from overheadlink.runtime import EnhancedOverheadLinkApp


def load_bootstrap_generator():
    path = PROJECT / "installer" / "prepare_bootstrap.py"
    spec = importlib.util.spec_from_file_location("prepare_bootstrap", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallerV039Tests(unittest.TestCase):
    def test_versions_are_aligned(self) -> None:
        with (PROJECT / "pyproject.toml").open("rb") as handle:
            project_version = str(tomllib.load(handle)["project"]["version"])
        self.assertEqual(__version__, project_version)

    def test_generated_installer_uses_project_version_and_forces_external_update_payload(self) -> None:
        with (PROJECT / "pyproject.toml").open("rb") as handle:
            project_version = str(tomllib.load(handle)["project"]["version"])
        module = load_bootstrap_generator()
        source = (PROJECT / "installer" / "bootstrap.c").read_text(encoding="utf-8")
        generated = module.build_source(source, project_version)
        self.assertIn(f'#define APP_VERSION L"{project_version}"', generated)
        self.assertIn(f'#define APP_VERSION_A "{project_version}"', generated)
        self.assertIn("strlen(APP_VERSION_A)", generated)
        self.assertIn('static const char value[] = APP_VERSION_A "\\r\\n";', generated)
        self.assertNotIn('APP_VERSION_A "\r\n";', generated)
        self.assertIn("!launched_from_external_installer && marker_matches(payload_marker)", generated)
        self.assertIn("OverheadLink-Setup", generated)
        self.assertNotIn("OverheadLink-Setup-v", generated)
        self.assertNotIn('strncmp(value, "0.3.6", 5)', generated)


class ResponsiveUsbScanTests(unittest.TestCase):
    def test_usb_scan_returns_without_waiting_for_slow_com_probe(self) -> None:
        class SlowBoardManager:
            def scan(self):
                time.sleep(0.20)
                return [object(), object()]

        class Status:
            def configure(self, **_kwargs):
                pass

        class Dummy:
            pass

        app = Dummy()
        app._scan_in_progress = False
        app._scan_requested = False
        app._scan_poll_scheduled = False
        app._scan_result_count = 0
        app._scan_error = ""
        app._scan_thread = None
        app.board_manager = SlowBoardManager()
        app.board_status = Status()
        app.after_calls = []
        app.after = lambda delay, callback: app.after_calls.append((delay, callback))
        app._schedule_scan_poll = EnhancedOverheadLinkApp._schedule_scan_poll.__get__(app, Dummy)
        app._poll_scan_completion = EnhancedOverheadLinkApp._poll_scan_completion.__get__(app, Dummy)
        app._refresh_connections = lambda: None
        app._log = lambda _message: None
        app._scan_boards = EnhancedOverheadLinkApp._scan_boards.__get__(app, Dummy)

        started = time.perf_counter()
        app._scan_boards()
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.08)
        self.assertTrue(app._scan_in_progress)
        self.assertIsNotNone(app._scan_thread)
        app._scan_thread.join(timeout=1.0)
        self.assertFalse(app._scan_in_progress)
        self.assertEqual(app._scan_result_count, 2)


if __name__ == "__main__":
    unittest.main()
