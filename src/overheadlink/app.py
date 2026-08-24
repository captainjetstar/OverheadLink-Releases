from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from queue import Empty, Queue
import shutil
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import uuid

from . import __version__
from .backlight import COLOUR_PRESETS, BacklightController, BacklightSettings, BrightnessPreset, ColourPreset
from .learning import AnalogLearningResult, AnalogLearningSession, DigitalLearningResult, DigitalLearningSession
from .models import BoardKind, PinAssignment, PinMode, VerificationStatus, canonical_pin
from .preferences import AppPreferences, canonical_port
from .profile import ProfileStore, ProfileValidator, issue_summary
from .protocol import ProtocolMessage
from .serial_manager import BoardManager, ConnectedBoard
from .simulator import FenixBridge, MockFenixBridge, SimulatorState
from .updater import UpdateInfo, download_update, is_newer, latest_release, launch_update


PROFILE_FILENAME = "a320_fenix_overhead.json"


def writable_data_root() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "OverheadLink"
    else:
        root = Path.home() / ".config" / "OverheadLink"
    root.mkdir(parents=True, exist_ok=True)
    return root


def bundled_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def writable_profile_path() -> Path:
    target = writable_data_root() / "profiles" / PROFILE_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        source = bundled_root() / "profiles" / PROFILE_FILENAME
        shutil.copy2(source, target)
    return target


class OverheadLinkApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"OverheadLink {__version__} — A320 Forward Overhead")
        self.geometry("1280x780")
        self.minsize(1050, 650)
        self.configure(bg="#111820")

        self.profile_store = ProfileStore(writable_profile_path())
        self.profile = self.profile_store.load()
        self.validator = ProfileValidator()
        self.issues = self.validator.validate(self.profile)
        self.event_queue: Queue[tuple[ConnectedBoard, ProtocolMessage]] = Queue()
        self.sim_event_queue: Queue[tuple[str, float]] = Queue()
        self.fenix_connect_queue: Queue[tuple[FenixBridge, str]] = Queue()
        self.update_queue: Queue[tuple[str, object]] = Queue()
        self.preferences = AppPreferences.load(writable_data_root() / "settings.json")
        self.board_manager = BoardManager(self._queue_board_message, ignored_ports=self.preferences.ignored_ports)
        self.fenix: FenixBridge = FenixBridge(self._on_fenix_feedback)
        self.learning: DigitalLearningSession | None = None
        self.analog_learning: AnalogLearningSession | None = None
        self.repair_target: tuple[str, str] | None = None
        self.selected_assignment: tuple[str, str] | None = None
        self.offline_fenix = tk.BooleanVar(value=False)
        self.configured_boards: set[str] = set()
        self.feedback_values: dict[str, float] = {}
        self.last_output_states: dict[tuple[str, str], bool] = {}
        self.fenix_subscribed = False
        self.fenix_connecting = False
        self.available_update: UpdateInfo | None = None
        self.update_busy = False

        self._configure_style()
        self._build_ui()
        self._refresh_profile_views()
        self._scan_boards()
        self._poll_events()
        self.after(1800, self._begin_fenix_connect)
        self.after(5000, self._auto_rescan)
        self.after(6000, lambda: self._check_for_updates(manual=False))
        self.after(15000, self._auto_runtime_tick)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#111820")
        style.configure("Card.TFrame", background="#18232e")
        style.configure("TLabel", background="#111820", foreground="#d9e3ec", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#111820", foreground="#f6a33b", font=("Segoe UI Semibold", 20))
        style.configure("Status.TLabel", background="#18232e", foreground="#d9e3ec", padding=8)
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(12, 8))
        style.configure("Preset.TButton", font=("Segoe UI Semibold", 12), padding=(18, 16))
        style.map("Preset.TButton", background=[("active", "#f6a33b")], foreground=[("active", "#101820")])
        style.configure("TNotebook", background="#111820", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI Semibold", 10), padding=(16, 10))
        style.configure("Treeview", background="#14202a", fieldbackground="#14202a", foreground="#d9e3ec", rowheight=26)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(20, 14))
        header.pack(fill="x")
        ttk.Label(header, text="OVERHEADLINK", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Standalone MSFS 2024 / Fenix overhead controller").pack(side="left", padx=(16, 0), pady=(9, 0))

        status = ttk.Frame(header, style="Card.TFrame")
        status.pack(side="right")
        self.board_status = ttk.Label(status, text="Boards: scanning", style="Status.TLabel")
        self.board_status.pack(side="left")
        self.sim_status = ttk.Label(status, text="Fenix: disconnected", style="Status.TLabel")
        self.sim_status.pack(side="left")
        errors, warnings = issue_summary(self.issues)
        self.profile_status = ttk.Label(status, text=f"Profile: {errors} errors / {warnings} warnings", style="Status.TLabel")
        self.profile_status.pack(side="left")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.connections_tab = ttk.Frame(self.tabs, padding=14)
        self.assign_tab = ttk.Frame(self.tabs, padding=14)
        self.backlight_tab = ttk.Frame(self.tabs, padding=14)
        self.debug_tab = ttk.Frame(self.tabs, padding=14)
        self.updates_tab = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(self.connections_tab, text="Connections")
        self.tabs.add(self.assign_tab, text="Assign Pins")
        self.tabs.add(self.backlight_tab, text="Backlighting")
        self.tabs.add(self.debug_tab, text="Live Debug")
        self.tabs.add(self.updates_tab, text="Updates")
        self._build_connections_tab()
        self._build_assign_tab()
        self._build_backlight_tab()
        self._build_debug_tab()
        self._build_updates_tab()

    def _build_updates_tab(self) -> None:
        card = ttk.Frame(self.updates_tab, style="Card.TFrame", padding=24)
        card.pack(fill="x")
        ttk.Label(card, text="OverheadLink Updates", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="Installed version", style="Status.TLabel").grid(row=1, column=0, sticky="w", pady=(20, 4))
        ttk.Label(card, text=f"v{__version__}", style="Status.TLabel").grid(row=1, column=1, sticky="w", pady=(20, 4))
        ttk.Label(card, text="Latest version", style="Status.TLabel").grid(row=2, column=0, sticky="w", pady=4)
        self.latest_version_var = tk.StringVar(value="Not checked yet")
        ttk.Label(card, textvariable=self.latest_version_var, style="Status.TLabel").grid(row=2, column=1, sticky="w", pady=4)
        self.update_status_var = tk.StringVar(value="Updates are checked automatically after startup.")
        ttk.Label(card, textvariable=self.update_status_var, style="Status.TLabel", wraplength=780).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(16, 12)
        )
        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.check_update_button = ttk.Button(buttons, text="Check for Updates", command=lambda: self._check_for_updates(manual=True))
        self.check_update_button.pack(side="left")
        self.install_update_button = ttk.Button(buttons, text="Download and Install Update", command=self._install_available_update, state="disabled")
        self.install_update_button.pack(side="left", padx=10)
        self.release_notes = tk.Text(
            card, height=11, wrap="word", bg="#14202a", fg="#d9e3ec", relief="flat", padx=12, pady=12
        )
        self.release_notes.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(18, 0))
        self.release_notes.insert("1.0", "Release notes will appear here when an update is available.")
        self.release_notes.configure(state="disabled")
        card.columnconfigure(1, weight=1)
        card.rowconfigure(5, weight=1)

    def _check_for_updates(self, *, manual: bool) -> None:
        if self.update_busy:
            return
        self.update_busy = True
        self.check_update_button.configure(state="disabled")
        self.update_status_var.set("Checking GitHub Releases…")

        def worker() -> None:
            try:
                self.update_queue.put(("checked", (manual, latest_release())))
            except Exception as error:
                self.update_queue.put(("check_error", (manual, str(error))))

        threading.Thread(target=worker, name="OverheadLink-UpdateCheck", daemon=True).start()

    def _install_available_update(self) -> None:
        update = self.available_update
        if update is None or self.update_busy:
            return
        if not messagebox.askyesno(
            "Install OverheadLink update",
            f"Install OverheadLink v{update.version} now?\n\nThe app will close, update itself, and reopen automatically.",
        ):
            return
        self.update_busy = True
        self.check_update_button.configure(state="disabled")
        self.install_update_button.configure(state="disabled")
        self.update_status_var.set(f"Downloading verified v{update.version} update…")

        def progress(received: int, total: int) -> None:
            self.update_queue.put(("progress", (received, total)))

        def worker() -> None:
            try:
                target = download_update(update, writable_data_root() / "updates", progress)
                self.update_queue.put(("downloaded", target))
            except Exception as error:
                self.update_queue.put(("download_error", str(error)))

        threading.Thread(target=worker, name="OverheadLink-UpdateDownload", daemon=True).start()

    def _show_release_notes(self, notes: str) -> None:
        self.release_notes.configure(state="normal")
        self.release_notes.delete("1.0", "end")
        self.release_notes.insert("1.0", notes)
        self.release_notes.configure(state="disabled")

    def _handle_update_event(self, event: str, payload: object) -> None:
        if event == "checked":
            manual, update = payload  # type: ignore[misc]
            assert isinstance(update, UpdateInfo)
            self.update_busy = False
            self.check_update_button.configure(state="normal")
            self.latest_version_var.set(f"v{update.version}")
            self._show_release_notes(update.notes)
            if is_newer(update.version, __version__):
                self.available_update = update
                self.install_update_button.configure(state="normal")
                self.update_status_var.set(f"OverheadLink v{update.version} is available and ready to install.")
                self._log(f"UPDATE AVAILABLE v{update.version}")
                if not manual:
                    self.tabs.select(self.updates_tab)
            else:
                self.available_update = None
                self.install_update_button.configure(state="disabled")
                self.update_status_var.set("OverheadLink is up to date.")
                self._log(f"UPDATE CHECK: v{__version__} is current")
            return
        if event == "check_error":
            manual, detail = payload  # type: ignore[misc]
            self.update_busy = False
            self.check_update_button.configure(state="normal")
            self.update_status_var.set("Could not check for updates. The app will continue working normally.")
            self._log(f"UPDATE CHECK FAILED: {detail}")
            if manual:
                messagebox.showwarning("Check for updates", f"The update check could not be completed:\n\n{detail}")
            return
        if event == "progress":
            received, total = payload  # type: ignore[misc]
            if total:
                self.update_status_var.set(f"Downloading update… {int(received) * 100 // int(total)}%")
            else:
                self.update_status_var.set(f"Downloading update… {int(received) // (1024 * 1024)} MB")
            return
        if event == "downloaded":
            target = Path(payload)  # type: ignore[arg-type]
            self.update_status_var.set("Update verified. Restarting OverheadLink…")
            self._log(f"UPDATE VERIFIED: {target.name}")
            try:
                launch_update(target)
            except Exception as error:
                self._handle_update_event("download_error", str(error))
                return
            self._close()
            return
        if event == "download_error":
            self.update_busy = False
            self.check_update_button.configure(state="normal")
            self.install_update_button.configure(state="normal" if self.available_update else "disabled")
            self.update_status_var.set("The update was not installed. Your existing version is unchanged.")
            self._log(f"UPDATE FAILED: {payload}")
            messagebox.showerror("OverheadLink update", f"The update could not be installed:\n\n{payload}")

    def _build_connections_tab(self) -> None:
        top = ttk.Frame(self.connections_tab)
        top.pack(fill="x", pady=(0, 10))
        ttk.Button(top, text="Rescan USB Boards", command=self._scan_boards).pack(side="left")
        ttk.Checkbutton(top, text="Offline Fenix simulation", variable=self.offline_fenix, command=self._toggle_fenix).pack(side="left", padx=14)
        ttk.Button(top, text="Connect to MSFS 2024", command=self._connect_fenix).pack(side="left")
        ttk.Button(top, text="Load All Online Maps", command=self._configure_all_boards).pack(side="left", padx=8)
        ttk.Button(top, text="Firmware Files", command=self._open_firmware_folder).pack(side="left")
        self.serial_note = ttk.Label(top, text="")
        self.serial_note.pack(side="right")

        columns = ("profile", "type", "port", "uuid", "firmware", "state")
        self.connections_tree = ttk.Treeview(self.connections_tab, columns=columns, show="headings", selectmode="browse")
        for column, heading, width in (
            ("profile", "Board identity", 230),
            ("type", "Hardware", 120),
            ("port", "Current port", 100),
            ("uuid", "Stable UUID", 170),
            ("firmware", "Firmware", 100),
            ("state", "State", 140),
        ):
            self.connections_tree.heading(column, text=heading)
            self.connections_tree.column(column, width=width, anchor="w")
        self.connections_tree.pack(fill="both", expand=True)
        self.connections_tree.bind("<Button-3>", self._show_connection_menu)

        ttk.Label(
            self.connections_tab,
            text="Right-click a COM port to assign it to an overhead panel or ignore it so MobiFlight, SL3, or Rowsfire can use it.",
            style="Status.TLabel",
        ).pack(fill="x", pady=(10, 0))

    def _build_assign_tab(self) -> None:
        split = ttk.Panedwindow(self.assign_tab, orient="horizontal")
        split.pack(fill="both", expand=True)
        left = ttk.Frame(split)
        right = ttk.Frame(split, style="Card.TFrame", padding=16)
        split.add(left, weight=4)
        split.add(right, weight=2)

        columns = ("board", "control", "role", "pin", "mode", "status")
        self.assignment_tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        for column, heading, width in (
            ("board", "Board", 180),
            ("control", "Control", 230),
            ("role", "Role", 130),
            ("pin", "Pin", 65),
            ("mode", "Mode", 120),
            ("status", "Verification", 140),
        ):
            self.assignment_tree.heading(column, text=heading)
            self.assignment_tree.column(column, width=width, anchor="w")
        self.assignment_tree.pack(fill="both", expand=True)
        self.assignment_tree.bind("<<TreeviewSelect>>", self._assignment_selected)

        ttk.Label(right, text="Selected assignment", style="Status.TLabel").pack(fill="x")
        self.assignment_detail = tk.Text(right, height=14, wrap="word", bg="#14202a", fg="#d9e3ec", insertbackground="white", relief="flat", padx=10, pady=10)
        self.assignment_detail.pack(fill="both", expand=True, pady=10)
        ttk.Button(right, text="Find Correct Pin", command=self._start_pin_repair).pack(fill="x", pady=4)
        ttk.Button(right, text="Finish Analogue Scan", command=self._finish_analog_repair).pack(fill="x", pady=4)
        ttk.Button(right, text="Pulse/Test Output Safely", command=self._test_selected_output).pack(fill="x", pady=4)
        ttk.Button(right, text="Find Correct Output Pin", command=self._find_output_pin).pack(fill="x", pady=4)
        ttk.Button(right, text="Load Validated Map to Board", command=self._configure_selected_board).pack(fill="x", pady=4)
        self.learning_status = ttk.Label(right, text="No learning session running", style="Status.TLabel", wraplength=330)
        self.learning_status.pack(fill="x", pady=(12, 0))

    def _build_backlight_tab(self) -> None:
        settings = BacklightSettings.from_dict(self.profile.backlighting)
        info = ttk.Label(
            self.backlight_tab,
            text="COM21 backlighting Nano · D6 WS2812B data · 300 LEDs · brightness and colour are stored automatically",
            style="Status.TLabel",
        )
        info.pack(fill="x", pady=(0, 10))
        buttons = ttk.Frame(self.backlight_tab)
        buttons.pack(fill="x")
        for preset in BrightnessPreset:
            ttk.Button(buttons, text=preset.value, style="Preset.TButton", command=lambda p=preset: self._apply_backlight(p)).pack(side="left", expand=True, fill="x", padx=6)

        editor = ttk.Frame(self.backlight_tab, style="Card.TFrame", padding=20)
        editor.pack(fill="x", pady=(12, 8))
        self.brightness_vars: dict[BrightnessPreset, tk.IntVar] = {
            BrightnessPreset.FULL_LIGHT: tk.IntVar(value=settings.full_light),
            BrightnessPreset.HALF_DIM: tk.IntVar(value=settings.half_dim),
            BrightnessPreset.DAY_TIME_DIM: tk.IntVar(value=settings.day_time_dim),
        }
        for row, preset in enumerate(BrightnessPreset):
            ttk.Label(editor, text=preset.value, style="Status.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=8)
            scale = ttk.Scale(editor, from_=0, to=255, orient="horizontal", variable=self.brightness_vars[preset])
            scale.grid(row=row, column=1, sticky="ew", pady=8)
            value = ttk.Label(editor, textvariable=self.brightness_vars[preset], style="Status.TLabel", width=5)
            value.grid(row=row, column=2, padx=(10, 0), pady=8)
        editor.columnconfigure(1, weight=1)
        ttk.Button(editor, text="Save Brightness Options", command=self._save_brightness).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(16, 0))

        colour_editor = ttk.Frame(self.backlight_tab, style="Card.TFrame", padding=16)
        colour_editor.pack(fill="x", pady=8)
        ttk.Label(colour_editor, text="Backlight colour presets", style="Status.TLabel").pack(anchor="w")
        colour_buttons = ttk.Frame(colour_editor, style="Card.TFrame")
        colour_buttons.pack(fill="x", pady=(8, 10))
        for preset, rgb in COLOUR_PRESETS.items():
            background = self._rgb_hex(rgb)
            foreground = "#111820" if sum(rgb) > 430 else "#ffffff"
            tk.Button(
                colour_buttons,
                text=preset.value,
                command=lambda selected=preset: self._apply_backlight_colour(selected),
                bg=background,
                fg=foreground,
                activebackground=background,
                activeforeground=foreground,
                relief="flat",
                font=("Segoe UI Semibold", 9),
                padx=8,
                pady=7,
            ).pack(side="left", expand=True, fill="x", padx=3)

        custom = ttk.Frame(colour_editor, style="Card.TFrame")
        custom.pack(fill="x")
        self.colour_vars: dict[str, tk.IntVar] = {
            "red": tk.IntVar(value=settings.red),
            "green": tk.IntVar(value=settings.green),
            "blue": tk.IntVar(value=settings.blue),
        }
        for column, (name, variable) in enumerate(self.colour_vars.items()):
            ttk.Label(custom, text=name.upper(), style="Status.TLabel").grid(row=0, column=column * 2, sticky="w", padx=(0, 4))
            ttk.Spinbox(custom, from_=0, to=255, textvariable=variable, width=5, command=self._refresh_colour_preview).grid(
                row=0, column=column * 2 + 1, sticky="w", padx=(0, 12)
            )
            variable.trace_add("write", lambda *_args: self._refresh_colour_preview())
        self.colour_preview = tk.Label(custom, text="", width=18, relief="flat", font=("Segoe UI Semibold", 9))
        self.colour_preview.grid(row=0, column=6, sticky="ew", padx=(8, 10))
        ttk.Button(custom, text="Apply Custom RGB", command=lambda: self._apply_backlight_colour(None)).grid(row=0, column=7, sticky="e")
        custom.columnconfigure(6, weight=1)
        self._refresh_colour_preview()

        self.backlight_status = ttk.Label(self.backlight_tab, text="Waiting for BACKLIGHT-NANO", style="Status.TLabel")
        self.backlight_status.pack(fill="x", pady=(8, 0))

    @staticmethod
    def _rgb_hex(rgb: tuple[int, int, int]) -> str:
        return "#" + "".join(f"{max(0, min(255, int(value))):02x}" for value in rgb)

    def _refresh_colour_preview(self) -> None:
        if not hasattr(self, "colour_preview"):
            return
        try:
            rgb = tuple(max(0, min(255, int(self.colour_vars[name].get()))) for name in ("red", "green", "blue"))
        except (tk.TclError, ValueError):
            return
        foreground = "#111820" if sum(rgb) > 430 else "#ffffff"
        self.colour_preview.configure(text=f"RGB {rgb[0]}, {rgb[1]}, {rgb[2]}", bg=self._rgb_hex(rgb), fg=foreground)

    def _build_debug_tab(self) -> None:
        toolbar = ttk.Frame(self.debug_tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Clear", command=lambda: self.debug_text.delete("1.0", "end")).pack(side="left")
        ttk.Button(toolbar, text="Export Log", command=self._export_log).pack(side="left", padx=8)
        self.debug_text = tk.Text(self.debug_tab, bg="#0b1117", fg="#a8f0b0", insertbackground="white", font=("Cascadia Mono", 9), relief="flat", padx=12, pady=12)
        self.debug_text.pack(fill="both", expand=True)
        self._log("OverheadLink started")
        for issue in self.issues:
            self._log(f"PROFILE {issue.level.upper()} {issue.board_id}: {issue.message}")

    def _scan_boards(self) -> None:
        boards = self.board_manager.scan()
        self._log(f"USB scan started: {len(boards)} candidate port(s)")
        self.after(1200, self._refresh_connections)

    def _auto_rescan(self) -> None:
        self.board_manager.scan()
        self._refresh_connections()
        self.after(5000, self._auto_rescan)

    def _refresh_connections(self) -> None:
        selected = tuple(self.connections_tree.selection())
        self.connections_tree.delete(*self.connections_tree.get_children())
        online = 0
        ports = set(self.board_manager.last_candidates) | set(self.board_manager.boards_by_port)
        for port in sorted(ports, key=str.casefold):
            candidate = self.board_manager.last_candidates.get(port)
            if self.board_manager.is_ignored(port):
                self.connections_tree.insert(
                    "",
                    "end",
                    iid=port,
                    values=("Ignored", candidate.description if candidate else "Serial device", port, "", "", "Ignored — free for other apps"),
                )
                continue
            board = self.board_manager.boards_by_port.get(port)
            if board is None:
                continue
            online += int(board.online)
            if board.online:
                state = "Online"
            elif board.connection and board.connection.running:
                state = "Identifying…"
            else:
                state = "Unavailable / in use"
            self.connections_tree.insert(
                "",
                "end",
                iid=port,
                values=(
                    board.board_name or "Unassigned",
                    board.board_type if board.board_type != "unknown" else (candidate.description if candidate else "Unknown"),
                    port,
                    board.board_uuid,
                    board.firmware,
                    state,
                ),
            )
        for port in selected:
            if self.connections_tree.exists(port):
                self.connections_tree.selection_add(port)
        expected = len([board for board in self.profile.boards if not board.optional])
        self.board_status.configure(text=f"Boards: {online} online / {expected} required")
        ignored = len(self.board_manager.ignored_ports)
        self.serial_note.configure(
            text=f"Serial ready · {ignored} ignored" if self.board_manager.serial_available else "Install pyserial to connect hardware"
        )

    def _show_connection_menu(self, event: tk.Event) -> None:
        port = self.connections_tree.identify_row(event.y)
        if not port:
            return
        self.connections_tree.selection_set(port)
        self.connections_tree.focus(port)
        menu = tk.Menu(self, tearoff=False)
        if self.board_manager.is_ignored(port):
            menu.add_command(label="Use this COM port in OverheadLink", command=lambda: self._use_port(port))
        else:
            board = self.board_manager.boards_by_port.get(port)
            detected_type = board.board_type.upper() if board else ""
            connected = bool(board and board.connection and board.connection.running)
            eligible = [
                profile_board
                for profile_board in self.profile.boards
                if (
                    detected_type == "MEGA" and profile_board.kind == BoardKind.MEGA
                ) or (
                    detected_type == "NANO" and profile_board.kind == BoardKind.BACKLIGHT_NANO
                )
            ]
            if connected and eligible:
                assign_menu = tk.Menu(menu, tearoff=False)
                for profile_board in eligible:
                    label = profile_board.name
                    if board and board.board_name.casefold() == profile_board.name.casefold():
                        label = f"✓ {label}"
                    assign_menu.add_command(
                        label=label,
                        command=lambda name=profile_board.name: self._assign_port_identity(port, name),
                    )
                menu.add_cascade(label="Assign to…", menu=assign_menu)
            else:
                menu.add_command(label="Assign to… (OverheadLink firmware not detected)", state="disabled")
            menu.add_separator()
            menu.add_command(label="Ignore this COM port", command=lambda: self._ignore_port(port))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _assign_port_identity(self, port: str, name: str) -> None:
        board = self.board_manager.boards_by_port.get(canonical_port(port))
        if board is None or board.connection is None or not board.connection.running:
            messagebox.showwarning("Assign panel", f"{port} is not available to OverheadLink.")
            return
        existing = self.board_manager.by_profile_name(name)
        if existing is not None and canonical_port(existing.port) != canonical_port(port):
            if not messagebox.askyesno(
                "Panel already assigned",
                f"{name} is already detected on {existing.port}.\n\nAssign {port} to {name} as well?",
            ):
                return
        stable_id = board.board_uuid if board.board_uuid and board.board_uuid != "UNSET" else uuid.uuid4().hex[:16].upper()
        board.connection.send(self._message("SET_ID", stable_id, name))
        self._log(f"RIGHT-CLICK ASSIGN: {board.port} -> {name} ({stable_id})")
        self.serial_note.configure(text=f"Assigning {port} to {name}…")

    def _ignore_port(self, port: str) -> None:
        normalized = canonical_port(port)
        try:
            self.preferences.ignore(normalized)
        except OSError as error:
            messagebox.showerror("Ignore COM port", f"The ignore setting could not be saved:\n{error}")
            return
        self.board_manager.ignore_port(normalized)
        self._log(f"COM PORT IGNORED: {normalized} — released for MobiFlight or another app")
        self._refresh_connections()

    def _use_port(self, port: str) -> None:
        normalized = canonical_port(port)
        try:
            self.preferences.use(normalized)
        except OSError as error:
            messagebox.showerror("Use COM port", f"The setting could not be saved:\n{error}")
            return
        self.board_manager.use_port(normalized)
        self._log(f"COM PORT ENABLED: {normalized}")
        self._scan_boards()

    def _open_firmware_folder(self) -> None:
        target = bundled_root() / "firmware"
        if os.name == "nt":
            try:
                os.startfile(target)  # type: ignore[attr-defined]
            except OSError as error:
                messagebox.showerror("Firmware files", f"Could not open:\n{target}\n\n{error}")
            return
        messagebox.showinfo("Firmware files", f"Firmware folder:\n{target}")

    def _toggle_fenix(self) -> None:
        if not self.offline_fenix.get():
            self._begin_fenix_connect(force=True)
            return
        self.fenix.close()
        self.fenix_subscribed = False
        self.fenix = MockFenixBridge(self._on_fenix_feedback)
        status = self.fenix.connect()
        self.sim_status.configure(text=f"Fenix: {status.detail}")
        self._log(status.detail)
        self._subscribe_profile_feedback()

    def _connect_fenix(self) -> None:
        self.offline_fenix.set(False)
        self._begin_fenix_connect(force=True)

    def _begin_fenix_connect(self, *, force: bool = False) -> None:
        if self.offline_fenix.get() or self.fenix_connecting:
            return
        if not force and self.fenix.status.state in {SimulatorState.MSFS_CONNECTED, SimulatorState.FENIX_CONNECTED}:
            return
        self.fenix_connecting = True
        self.sim_status.configure(text="Fenix: connecting automatically…")
        self._log("Automatic MSFS 2024 / Fenix connection started")

        def connect_worker() -> None:
            bridge = FenixBridge(self._on_fenix_feedback)
            status = bridge.connect()
            self.fenix_connect_queue.put((bridge, status.detail))

        threading.Thread(target=connect_worker, name="OverheadLink-FenixConnect", daemon=True).start()

    def _auto_runtime_tick(self) -> None:
        if (
            not self.offline_fenix.get()
            and not self.fenix_connecting
            and self.fenix.status.state in {SimulatorState.DISCONNECTED, SimulatorState.ERROR}
        ):
            self._begin_fenix_connect()
        self.after(15000, self._auto_runtime_tick)

    def _subscribe_profile_feedback(self) -> None:
        if self.fenix_subscribed or self.fenix.status.state != SimulatorState.FENIX_CONNECTED:
            return
        subscribed = 0
        for board in self.profile.boards:
            for assignment in board.assignments:
                if not assignment.enabled or not assignment.sim.verified or not assignment.sim.feedback:
                    continue
                try:
                    self.fenix.subscribe(assignment.id, assignment.sim.feedback)
                    subscribed += 1
                except RuntimeError as error:
                    self._log(f"FENIX SUBSCRIBE BLOCKED {assignment.id}: {error}")
        self.fenix_subscribed = True
        self._log(f"FENIX feedback subscriptions: {subscribed}")
        for board_id in tuple(self.configured_boards):
            board = self.profile.board(board_id)
            connected = self.board_manager.by_profile_name(board.name) if board else None
            if connected and connected.online and connected.connection:
                connected.connection.send(self._message("SNAPSHOT"))

    def _refresh_profile_views(self) -> None:
        self.issues = self.validator.validate(self.profile)
        errors, warnings = issue_summary(self.issues)
        self.profile_status.configure(text=f"Profile: {errors} errors / {warnings} warnings")
        self.assignment_tree.delete(*self.assignment_tree.get_children())
        for board in self.profile.boards:
            for assignment in board.assignments:
                if assignment.status == VerificationStatus.SUPERSEDED:
                    continue
                iid = f"{board.id}::{assignment.id}"
                self.assignment_tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(board.name, assignment.control, assignment.role.value, assignment.pin, assignment.mode.value, assignment.status.value),
                )

    def _assignment_selected(self, _event: object = None) -> None:
        selection = self.assignment_tree.selection()
        if not selection:
            return
        board_id, assignment_id = selection[0].split("::", 1)
        self.selected_assignment = (board_id, assignment_id)
        board = self.profile.board(board_id)
        assignment = board.assignment(assignment_id) if board else None
        if board is None or assignment is None:
            return
        detail = {
            "Board": board.name,
            "Control": assignment.control,
            "Role": assignment.role.value,
            "Pin": assignment.pin,
            "Mode": assignment.mode.value,
            "Verification": assignment.status.value,
            "Source": assignment.source_revision,
            "Fenix press": assignment.sim.on_press or "Not assigned",
            "Fenix feedback": assignment.sim.feedback or "Not assigned",
            "Notes": assignment.notes or "None",
        }
        self.assignment_detail.delete("1.0", "end")
        self.assignment_detail.insert("1.0", "\n".join(f"{key}: {value}" for key, value in detail.items()))

    def _start_pin_repair(self) -> None:
        if self.selected_assignment is None:
            messagebox.showinfo("Find Correct Pin", "Select an assignment first.")
            return
        board_id, assignment_id = self.selected_assignment
        board = self.profile.board(board_id)
        assignment = board.assignment(assignment_id) if board else None
        if assignment is None or assignment.mode not in {PinMode.DIGITAL_INPUT, PinMode.ANALOG_INPUT}:
            messagebox.showinfo("Find Correct Pin", "Select a switch, selector contact, rotary contact, or potentiometer. Outputs use the safe pulse test.")
            return
        for connected in self.board_manager.boards_by_port.values():
            if connected.online and connected.connection:
                connected.connection.send(self._message("LEARN_IN", 0))
                connected.connection.send(self._message("LEARN_ANALOG", 0))
        if assignment.mode == PinMode.ANALOG_INPUT:
            self.learning = None
            self.analog_learning = AnalogLearningSession()
            self.repair_target = (board_id, assignment_id)
            for connected in self.board_manager.boards_by_port.values():
                if connected.online and connected.board_type.upper() == "MEGA" and connected.connection:
                    connected.connection.send(self._message("LEARN_ANALOG", 1))
            self.learning_status.configure(
                text=f"Move {assignment.control} slowly through its full travel twice, then click Finish Analogue Scan."
            )
            self._log(f"ANALOG PIN SEARCH started for {assignment.control} (saved {board.name} {assignment.pin})")
            return
        self.analog_learning = None
        self.learning = DigitalLearningSession()
        self.repair_target = (board_id, assignment_id)
        for connected in self.board_manager.boards_by_port.values():
            if connected.online and connected.board_type.upper() == "MEGA" and connected.connection:
                connected.connection.send(self._message("LEARN_IN", 1))
        self.learning_status.configure(text=f"Operate {assignment.control} twice. Monitoring every connected Mega for the actual pin…")
        self._log(f"PIN SEARCH started for {assignment.control} (saved {assignment.pin})")

    def _finish_analog_repair(self) -> None:
        if self.analog_learning is None or self.repair_target is None:
            messagebox.showinfo("Analogue scan", "Start Find Correct Pin on a potentiometer first.")
            return
        for connected in self.board_manager.boards_by_port.values():
            if connected.online and connected.connection:
                connected.connection.send(self._message("LEARN_ANALOG", 0))
        try:
            result = self.analog_learning.finalize()
        except ValueError as error:
            self.learning_status.configure(text=f"Analogue scan incomplete: {error}")
            messagebox.showwarning("Analogue scan incomplete", str(error))
            self.analog_learning = None
            self.repair_target = None
            return
        self._complete_analog_repair(result)

    def _complete_analog_repair(self, result: AnalogLearningResult) -> None:
        if self.repair_target is None:
            return
        source_board_id, assignment_id = self.repair_target
        source = self.profile.board(source_board_id)
        assignment = source.assignment(assignment_id) if source else None
        target = next((board for board in self.profile.boards if board.name.casefold() == result.board_id.casefold()), None)
        if assignment is None or target is None:
            return
        text = (
            f"{assignment.control} was saved as {source.name} {assignment.pin}.\n\n"
            f"Detected: {target.name} {result.pin}\n"
            f"Range: {result.minimum}..{result.maximum}\n"
            f"Noise: {result.noise:.2f}\n"
            f"Confidence: {result.confidence:.0%}\n\nApply this correction and calibration?"
        )
        if messagebox.askyesno("Correct analogue pin found", text):
            calibration = {
                "minimum": result.minimum,
                "maximum": result.maximum,
                "centre": result.centre,
                "noise": result.noise,
                "inverted": result.inverted,
            }
            old_board, old_pin, new_board, new_pin = self.profile_store.repair_assignment(
                self.profile,
                source_board_id,
                assignment_id,
                target.id,
                result.pin,
                f"Analogue full-travel scan at {result.confidence:.0%} confidence",
                calibration=calibration,
            )
            self.configured_boards.discard(source_board_id)
            self.configured_boards.discard(target.id)
            self.selected_assignment = (target.id, assignment_id)
            self._log(f"ANALOG PIN REPAIRED {assignment.control}: {old_board} {old_pin} -> {new_board} {new_pin}")
            self._refresh_profile_views()
        self.analog_learning = None
        self.repair_target = None
        self.learning_status.configure(text="Analogue pin search complete")

    def _test_selected_output(self) -> None:
        if self.selected_assignment is None:
            return
        board_id, assignment_id = self.selected_assignment
        board = self.profile.board(board_id)
        assignment = board.assignment(assignment_id) if board else None
        if board is None or assignment is None or assignment.mode != PinMode.DIGITAL_OUTPUT:
            messagebox.showinfo("Output test", "Select an LED output first.")
            return
        if board.id not in self.configured_boards:
            load = messagebox.askyesno(
                "Load validated map",
                f"{board.name} must load its validated map before an output can be tested. Load it now?",
            )
            if not load or not self._configure_board(board.id, show_warnings=True):
                return
        connected = self.board_manager.by_profile_name(board.name)
        if connected is None or not connected.online or connected.connection is None:
            messagebox.showwarning("Output test", f"{board.name} is not online.")
            return
        connected.connection.send(self._message("APPROVE_OUT", assignment.numeric_pin))
        connected.connection.send(self._message("PULSE", assignment.numeric_pin, 500))
        self._log(f"Safe output pulse: {board.name} {assignment.pin} {assignment.control}")

    def _find_output_pin(self) -> None:
        if self.selected_assignment is None:
            messagebox.showinfo("Find output pin", "Select an annunciator LED assignment first.")
            return
        board_id, assignment_id = self.selected_assignment
        board = self.profile.board(board_id)
        assignment = board.assignment(assignment_id) if board else None
        if board is None or assignment is None or assignment.mode != PinMode.DIGITAL_OUTPUT:
            messagebox.showinfo("Find output pin", "Select an annunciator LED output first.")
            return
        if board.id not in self.configured_boards and not self._configure_board(board.id, show_warnings=True):
            return
        connected = self.board_manager.by_profile_name(board.name)
        if connected is None or not connected.online or connected.connection is None:
            return
        outputs = [
            item
            for item in board.assignments
            if item.enabled and item.status != VerificationStatus.SUPERSEDED and item.mode == PinMode.DIGITAL_OUTPUT
        ]
        outputs.sort(key=lambda item: (item is not assignment, item.numeric_pin))
        for candidate in outputs:
            connected.connection.send(self._message("PULSE", candidate.numeric_pin, 1200))
            self._log(f"OUTPUT SEARCH pulse {board.name} {candidate.pin} for {assignment.control}")
            if not messagebox.askyesno(
                f"Testing {candidate.pin}",
                f"Did {assignment.control} illuminate from {board.name} {candidate.pin}?",
            ):
                continue
            if candidate is assignment:
                messagebox.showinfo("Output pin confirmed", f"The saved pin {assignment.pin} is correct.")
                self._log(f"OUTPUT CONFIRMED {assignment.control}: {board.name} {assignment.pin}")
                return
            swap = messagebox.askyesno(
                "Swap output assignments",
                f"{candidate.pin} is currently assigned to {candidate.control}.\n\n"
                f"Swap the pins for these two output assignments?",
            )
            if not swap:
                return
            old_pin, found_pin = self.profile_store.swap_output_pins(
                self.profile,
                board.id,
                assignment.id,
                candidate.id,
                "Confirmed by two-LED safe output search",
            )
            self.last_output_states.pop((board.id, assignment.id), None)
            self.last_output_states.pop((board.id, candidate.id), None)
            self._refresh_profile_views()
            self._configure_board(board.id, show_warnings=True)
            self._log(
                f"OUTPUT PIN SWAP {assignment.control}: {old_pin}->{found_pin}; "
                f"{candidate.control}: {found_pin}->{old_pin}"
            )
            messagebox.showinfo("Output repaired", f"{assignment.control} is now assigned to {found_pin}.")
            return
        messagebox.showwarning(
            "Output not found",
            "The correct lamp was not found in this board's validated output-pin pool. "
            "No unknown or input-designated pin was driven, and no change was saved.",
        )

    def _configure_selected_board(self) -> None:
        if self.selected_assignment is None:
            return
        board_id, _ = self.selected_assignment
        board = self.profile.board(board_id)
        if board is None or board.kind != BoardKind.MEGA:
            return
        self._configure_board(board_id, show_warnings=True)

    def _configure_all_boards(self) -> None:
        loaded = 0
        for board in self.profile.boards:
            if board.kind == BoardKind.MEGA and self._configure_board(board.id, show_warnings=False):
                loaded += 1
        if loaded == 0:
            messagebox.showinfo("Load maps", "No identified, validated Mega boards are currently online.")
        else:
            self._log(f"Validated maps loaded onto {loaded} online Mega board(s)")

    def _configure_board(self, board_id: str, *, show_warnings: bool) -> bool:
        board = self.profile.board(board_id)
        if board is None or board.kind != BoardKind.MEGA:
            return False
        board_issues = [issue for issue in self.validator.validate(self.profile) if issue.board_id == board_id and issue.level == "error"]
        if board_issues:
            if show_warnings:
                messagebox.showerror("Profile blocked", "This board has profile errors. Resolve them before loading the map.")
            return False
        connected = self.board_manager.by_profile_name(board.name)
        if connected is None or not connected.online or connected.connection is None:
            if show_warnings:
                messagebox.showwarning("Board offline", f"{board.name} is not online.")
            return False
        connected.connection.send(self._message("SAFE"))
        outputs: list[PinAssignment] = []
        for assignment in board.assignments:
            if not assignment.enabled or assignment.status == VerificationStatus.SUPERSEDED:
                continue
            mode = {PinMode.DIGITAL_INPUT: "I", PinMode.ANALOG_INPUT: "A", PinMode.DIGITAL_OUTPUT: "O"}.get(assignment.mode)
            if mode is None:
                continue
            connected.connection.send(self._message("CONFIG", assignment.numeric_pin, mode, int(assignment.active_low), assignment.debounce_ms))
            if assignment.mode == PinMode.DIGITAL_OUTPUT:
                outputs.append(assignment)
        for assignment in outputs:
            connected.connection.send(self._message("APPROVE_OUT", assignment.numeric_pin))
        connected.connection.send(self._message("RUN"))
        self.configured_boards.add(board.id)
        for assignment in outputs:
            if assignment.id in self.feedback_values:
                self.last_output_states.pop((board.id, assignment.id), None)
                self._process_fenix_feedback(assignment.id, self.feedback_values[assignment.id])
        self._log(f"Validated map loaded: {board.name} ({len(board.assignments)} assignments)")
        return True

    def _apply_backlight(self, preset: BrightnessPreset) -> None:
        nano_profile = next((board for board in self.profile.boards if board.kind == BoardKind.BACKLIGHT_NANO), None)
        if nano_profile is None:
            return
        connected = self.board_manager.by_profile_name(nano_profile.name)
        if connected is None or not connected.online or connected.connection is None:
            messagebox.showwarning("Backlighting Nano", "BACKLIGHT-NANO is not online. It will still illuminate at its saved startup preset when powered.")
            return
        settings = BacklightSettings.from_dict(self.profile.backlighting)
        settings.full_light = self.brightness_vars[BrightnessPreset.FULL_LIGHT].get()
        settings.half_dim = self.brightness_vars[BrightnessPreset.HALF_DIM].get()
        settings.day_time_dim = self.brightness_vars[BrightnessPreset.DAY_TIME_DIM].get()
        controller = BacklightController(connected.connection.send, settings)
        value = controller.apply(preset)
        self.backlight_status.configure(text=f"{preset.value} active — brightness {value}/255")
        self._log(f"BACKLIGHT {preset.value}: {value}/255")

    def _apply_backlight_colour(self, preset: ColourPreset | None) -> None:
        if preset is None:
            try:
                rgb = tuple(int(self.colour_vars[name].get()) for name in ("red", "green", "blue"))
            except (tk.TclError, ValueError):
                messagebox.showerror("Backlight colour", "Red, green and blue must each be numbers from 0 to 255.")
                return
            preset_name = "CUSTOM"
        else:
            rgb = COLOUR_PRESETS[preset]
            preset_name = preset.value
            for name, value in zip(("red", "green", "blue"), rgb):
                self.colour_vars[name].set(value)
        if any(not 0 <= value <= 255 for value in rgb):
            messagebox.showerror("Backlight colour", "Red, green and blue must each be between 0 and 255.")
            return
        self.profile.backlighting["colour"] = {"red": rgb[0], "green": rgb[1], "blue": rgb[2]}
        self.profile.backlighting["colourPreset"] = preset_name
        self.profile_store.save(self.profile, f"Backlight colour changed to {preset_name}: RGB {rgb}")
        self._refresh_colour_preview()
        if self._send_backlight_colour(rgb):
            self.backlight_status.configure(text=f"{preset_name} active — RGB {rgb[0]}, {rgb[1]}, {rgb[2]}")
            self._log(f"BACKLIGHT COLOUR {preset_name}: RGB {rgb[0]},{rgb[1]},{rgb[2]}")
        else:
            self.backlight_status.configure(text=f"{preset_name} saved — it will apply when BACKLIGHT-NANO connects")

    def _send_backlight_colour(self, rgb: tuple[int, int, int]) -> bool:
        nano_profile = next((board for board in self.profile.boards if board.kind == BoardKind.BACKLIGHT_NANO), None)
        connected = self.board_manager.by_profile_name(nano_profile.name) if nano_profile else None
        if connected is None or not connected.online or connected.connection is None:
            return False
        settings = BacklightSettings.from_dict(self.profile.backlighting)
        controller = BacklightController(connected.connection.send, settings)
        controller.apply_colour(*rgb)
        return True

    def _save_brightness(self) -> None:
        values = {preset.value: int(variable.get()) for preset, variable in self.brightness_vars.items()}
        if any(not 0 <= value <= 255 for value in values.values()):
            messagebox.showerror("Brightness", "Every brightness must be between 0 and 255.")
            return
        self.profile.backlighting.setdefault("presets", {}).update(values)
        self.profile_store.save(self.profile, f"Backlight presets updated: {values}")
        self.backlight_status.configure(text="Brightness options saved")
        self._log(f"BACKLIGHT presets saved: {values}")

    def _queue_board_message(self, board: ConnectedBoard, message: ProtocolMessage) -> None:
        self.event_queue.put((board, message))

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.update_queue.get_nowait()
                self._handle_update_event(event, payload)
        except Empty:
            pass
        try:
            while True:
                bridge, detail = self.fenix_connect_queue.get_nowait()
                self.fenix_connecting = False
                if self.offline_fenix.get():
                    bridge.close()
                    continue
                old_bridge = self.fenix
                self.fenix = bridge
                self.fenix_subscribed = False
                old_bridge.close()
                self.sim_status.configure(text=f"Fenix: {detail}")
                self._log(detail)
                self._subscribe_profile_feedback()
        except Empty:
            pass
        try:
            while True:
                board, message = self.event_queue.get_nowait()
                self._handle_board_message(board, message)
        except Empty:
            pass
        try:
            while True:
                assignment_id, value = self.sim_event_queue.get_nowait()
                self._process_fenix_feedback(assignment_id, value)
        except Empty:
            pass
        self._subscribe_profile_feedback()
        if not self.fenix_connecting:
            self.sim_status.configure(text=f"Fenix: {self.fenix.status.detail}")
        self.after(250, self._poll_events)

    def _handle_board_message(self, board: ConnectedBoard, message: ProtocolMessage) -> None:
        self._log(f"{board.port} {message.message_type} {' '.join(message.parts)}")
        if message.message_type == "IDENT":
            profile_board = next(
                (item for item in self.profile.boards if item.name.casefold() == board.board_name.casefold()),
                None,
            )
            if profile_board is not None:
                self.configured_boards.discard(profile_board.id)
                if profile_board.kind == BoardKind.MEGA:
                    self.after(350, lambda board_id=profile_board.id: self._auto_configure_board(board_id))
                elif profile_board.kind == BoardKind.BACKLIGHT_NANO and board.connection:
                    board.connection.send(self._message("STATUS"))
                    colour = BacklightSettings.from_dict(self.profile.backlighting)
                    self._send_backlight_colour((colour.red, colour.green, colour.blue))
            self._refresh_connections()
            return
        if message.message_type == "DIN" and len(message.parts) >= 3:
            pin = int(message.parts[0])
            value = bool(int(message.parts[1]))
            if self.learning and not self.learning.expired:
                result = self.learning.observe(board.board_name or board.port, pin, value)
                if result:
                    self._complete_repair(result)
            self._dispatch_input(board, pin, value)
        elif message.message_type == "AIN" and len(message.parts) >= 3:
            pin = int(message.parts[0])
            value = int(message.parts[1])
            self._log(f"ANALOG {board.board_name} {canonical_pin(pin)} = {value}")
            if self.analog_learning is not None:
                self.analog_learning.observe(board.board_name or board.port, pin, value)
        elif message.message_type == "PRESET" and len(message.parts) >= 2:
            self.backlight_status.configure(text=f"Nano reports {message.parts[0]} — {message.parts[1]}/255")
        elif message.message_type == "ACK" and message.parts and message.parts[0] == "COLOR":
            self._log("BACKLIGHT-NANO confirmed colour change")

    def _complete_repair(self, result: DigitalLearningResult) -> None:
        if self.repair_target is None:
            return
        board_id, assignment_id = self.repair_target
        target_board = self.profile.board(board_id)
        assignment = target_board.assignment(assignment_id) if target_board else None
        actual_board = next((board for board in self.profile.boards if board.name.casefold() == result.board_id.casefold()), None)
        if assignment is None or actual_board is None:
            return
        proposed_pin = result.pin
        text = f"{assignment.control} was saved as {assignment.pin}.\n\nDetected: {actual_board.name} {proposed_pin}\nConfidence: {result.confidence:.0%}\n\nApply this correction?"
        apply = messagebox.askyesno("Correct pin found", text)
        if apply:
            old_board, old_pin, new_board, new_pin = self.profile_store.repair_assignment(
                self.profile,
                board_id,
                assignment_id,
                actual_board.id,
                proposed_pin,
                f"Auto-learned twice at {result.confidence:.0%} confidence",
                active_low=result.active_low,
            )
            self.configured_boards.discard(board_id)
            self.configured_boards.discard(actual_board.id)
            self.selected_assignment = (actual_board.id, assignment_id)
            self._log(f"PIN REPAIRED {assignment.control}: {old_board} {old_pin} -> {new_board} {new_pin}")
            self._refresh_profile_views()
        for connected in self.board_manager.boards_by_port.values():
            if connected.online and connected.connection:
                connected.connection.send(self._message("LEARN_IN", 0))
        self.learning = None
        self.repair_target = None
        self.learning_status.configure(text="Pin search complete")

    def _dispatch_input(self, connected: ConnectedBoard, numeric_pin: int, raw_value: bool) -> None:
        board = next((item for item in self.profile.boards if item.name.casefold() == connected.board_name.casefold()), None)
        if board is None:
            return
        assignment = next((item for item in board.assignments if item.enabled and item.numeric_pin == numeric_pin and item.mode == PinMode.DIGITAL_INPUT), None)
        if assignment is None:
            return
        active = not raw_value if assignment.active_low else raw_value
        self._log(f"TRACE {assignment.control}: raw={int(raw_value)} active={int(active)} pin={assignment.pin}")
        if active and assignment.sim.on_press:
            try:
                self.fenix.execute(assignment.sim.on_press)
                self._log(f"FENIX SEND {assignment.id}: {assignment.sim.on_press}")
            except RuntimeError as error:
                self._log(f"FENIX BLOCKED {assignment.id}: {error}")
        if not active and assignment.sim.on_release:
            try:
                self.fenix.execute(assignment.sim.on_release)
            except RuntimeError as error:
                self._log(f"FENIX BLOCKED {assignment.id}: {error}")

    def _on_fenix_feedback(self, assignment_id: str, value: float) -> None:
        # SimConnect callbacks arrive on a worker thread; Tk and serial-output
        # decisions stay on the UI thread through this queue.
        self.sim_event_queue.put((assignment_id, value))

    def _auto_configure_board(self, board_id: str) -> None:
        if board_id in self.configured_boards:
            return
        if self._configure_board(board_id, show_warnings=False):
            board = self.profile.board(board_id)
            if board is not None:
                self._log(f"AUTO START ready: {board.name}")

    def _process_fenix_feedback(self, assignment_id: str, value: float) -> None:
        self.feedback_values[assignment_id] = value
        found = next(
            (
                (board, assignment)
                for board in self.profile.boards
                for assignment in board.assignments
                if assignment.id == assignment_id
            ),
            None,
        )
        if found is None:
            self._log(f"FENIX FEEDBACK unknown {assignment_id} = {value}")
            return
        board, assignment = found
        self._log(f"FENIX FEEDBACK {assignment_id} = {value}")
        if assignment.mode != PinMode.DIGITAL_OUTPUT or board.id not in self.configured_boards:
            return
        connected = self.board_manager.by_profile_name(board.name)
        if connected is None or not connected.online or connected.connection is None:
            return
        active = abs(value) > 0.00001
        state_key = (board.id, assignment.id)
        if self.last_output_states.get(state_key) == active:
            return
        connected.connection.send(self._message("SET", assignment.numeric_pin, int(active)))
        self.last_output_states[state_key] = active
        self._log(f"ANNUNCIATOR {board.name} {assignment.pin} {assignment.control} = {int(active)}")

    def _export_log(self) -> None:
        output = writable_profile_path().parent.parent / "logs"
        output.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = output / f"OverheadLink_Debug_{stamp}.log"
        target.write_text(self.debug_text.get("1.0", "end-1c") + "\n", encoding="utf-8")
        messagebox.showinfo("Debug log", f"Saved:\n{target}")

    def _log(self, message: str) -> None:
        if not hasattr(self, "debug_text"):
            return
        line = f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  {message}\n"
        self.debug_text.insert("end", line)
        self.debug_text.see("end")

    @staticmethod
    def _message(message_type: str, *parts: object) -> bytes:
        from .protocol import encode_message

        return encode_message(message_type, *parts)

    def _close(self) -> None:
        self.fenix.close()
        self.board_manager.stop()
        self.destroy()


def main() -> None:
    app = OverheadLinkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
