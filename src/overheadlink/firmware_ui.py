from __future__ import annotations

from queue import Empty, Queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .app import bundled_root
from .bootstrap import prepare_profile
from .firmware_update import FirmwareFlashError, FirmwareFlasher, FirmwareTarget, TARGET_LABELS
from .preferences import canonical_port
from .runtime import EnhancedOverheadLinkApp
from .v0310_fix import ensure_adirs_required


class FirmwareEnabledOverheadLinkApp(EnhancedOverheadLinkApp):
    """EnhancedOverheadLinkApp with an in-app Arduino firmware recovery tool."""

    def __init__(self) -> None:
        self._firmware_busy = False
        self._firmware_port = ""
        self._firmware_target: FirmwareTarget | None = None
        self._firmware_queue: Queue[tuple[str, object]] = Queue()
        self._firmware_poll_scheduled = False
        self._firmware_flasher = FirmwareFlasher(bundled_root())
        super().__init__()

    def _build_connections_tab(self) -> None:
        super()._build_connections_tab()

        card = ttk.Frame(self.connections_tab, style="Card.TFrame", padding=(14, 12))
        card.pack(fill="x", pady=(10, 0))
        ttk.Label(card, text="Firmware Updater", style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            card,
            text="Select a COM port above. This can recover a board even when it is stuck on Identifying…",
            style="Status.TLabel",
        ).grid(row=0, column=1, columnspan=3, sticky="w")

        ttk.Label(card, text="Board type", style="Status.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.firmware_target_var = tk.StringVar(value="Mega 2560")
        self.firmware_target_combo = ttk.Combobox(
            card,
            textvariable=self.firmware_target_var,
            values=tuple(TARGET_LABELS),
            state="readonly",
            width=20,
        )
        self.firmware_target_combo.grid(row=1, column=1, sticky="w", padx=(6, 12), pady=(8, 0))
        self.firmware_flash_button = ttk.Button(
            card,
            text="Flash Selected COM Port",
            command=self._flash_selected_firmware,
        )
        self.firmware_flash_button.grid(row=1, column=2, sticky="w", pady=(8, 0))
        self.firmware_status_var = tk.StringVar(
            value="Bundled firmware is ready. No Arduino IDE is required for flashing."
        )
        ttk.Label(
            card,
            textvariable=self.firmware_status_var,
            style="Status.TLabel",
            wraplength=520,
        ).grid(row=1, column=3, sticky="ew", padx=(12, 0), pady=(8, 0))
        card.columnconfigure(3, weight=1)

        self.connections_tree.bind("<<TreeviewSelect>>", self._firmware_selection_changed, add="+")

    def _firmware_selection_changed(self, _event: object = None) -> None:
        selection = self.connections_tree.selection()
        if not selection:
            return
        port = canonical_port(selection[0])
        board = self.board_manager.boards_by_port.get(port)
        if board is None:
            return
        detected = board.board_type.upper()
        if detected == "MEGA":
            self.firmware_target_var.set("Mega 2560")
        elif detected == "NANO":
            self.firmware_target_var.set("Backlight Nano")

    def _flash_selected_firmware(self) -> None:
        if self._firmware_busy:
            return
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showwarning("Firmware updater", "Select the COM port you want to flash first.")
            return
        port = canonical_port(selection[0])
        if self.board_manager.is_ignored(port):
            messagebox.showwarning(
                "Firmware updater",
                f"{port} is currently ignored. Right-click it and choose 'Use this COM port in OverheadLink' first.",
            )
            return

        target = TARGET_LABELS.get(self.firmware_target_var.get())
        if target is None:
            messagebox.showerror("Firmware updater", "Choose a valid board type.")
            return

        board = self.board_manager.boards_by_port.get(port)
        detected = board.board_type.upper() if board else ""
        if detected in {"MEGA", "NANO"} and detected != target.board_type:
            messagebox.showerror(
                "Firmware updater",
                f"{port} identifies as {detected}. Refusing to flash {target.label} firmware to the wrong controller.",
            )
            return

        missing = self._firmware_flasher.missing_assets(target)
        if missing:
            detail = "\n".join(str(path) for path in missing)
            messagebox.showerror(
                "Firmware updater unavailable",
                "This OverheadLink installation does not contain the bundled flashing files.\n\n"
                f"Missing:\n{detail}\n\nInstall the latest OverheadLink release and try again.",
            )
            return

        if not messagebox.askyesno(
            "Flash OverheadLink firmware",
            f"Flash {target.label} firmware v{target.firmware_version} to {port}?\n\n"
            "This replaces the sketch currently on that controller. The OverheadLink panel identity and settings "
            "stored in EEPROM are preserved. Do not unplug the USB cable while the firmware is being written.",
        ):
            return

        self._firmware_busy = True
        self._firmware_port = port
        self._firmware_target = target
        self.firmware_flash_button.configure(state="disabled")
        self.firmware_target_combo.configure(state="disabled")
        self.firmware_status_var.set(f"Preparing {port} for firmware update…")
        self._log(f"FIRMWARE UPDATE requested: {port} -> {target.label} v{target.firmware_version}")
        self._begin_firmware_flash_when_ready()

    def _begin_firmware_flash_when_ready(self) -> None:
        if not self._firmware_busy or self._firmware_target is None:
            return
        if self._scan_in_progress:
            self.firmware_status_var.set("Waiting for the current USB scan to finish…")
            self.after(120, self._begin_firmware_flash_when_ready)
            return

        port = self._firmware_port
        target = self._firmware_target
        # Temporarily ignore the port only in BoardManager memory. This closes
        # OverheadLink's serial handle and prevents the automatic scanner from
        # stealing the port back while avrdude is using it.
        self.board_manager.ignore_port(port)
        self.firmware_status_var.set(f"{port} released. Starting bundled firmware flasher…")

        def progress(message: str) -> None:
            self._firmware_queue.put(("progress", message))

        def worker() -> None:
            try:
                result = self._firmware_flasher.flash(port, target, progress)
                self._firmware_queue.put(("success", result))
            except (FirmwareFlashError, OSError, RuntimeError) as error:
                self._firmware_queue.put(("error", str(error)))

        threading.Thread(target=worker, name=f"OverheadLink-Firmware-{port}", daemon=True).start()
        self._schedule_firmware_poll()

    def _schedule_firmware_poll(self) -> None:
        if self._firmware_poll_scheduled:
            return
        self._firmware_poll_scheduled = True
        self.after(100, self._poll_firmware_events)

    def _poll_firmware_events(self) -> None:
        self._firmware_poll_scheduled = False
        finished = False
        while True:
            try:
                event, payload = self._firmware_queue.get_nowait()
            except Empty:
                break
            if event == "progress":
                self.firmware_status_var.set(str(payload))
                continue
            if event == "success":
                finished = True
                self._finish_firmware_flash(success=True, payload=payload)
                break
            if event == "error":
                finished = True
                self._finish_firmware_flash(success=False, payload=payload)
                break
        if self._firmware_busy and not finished:
            self._schedule_firmware_poll()

    def _finish_firmware_flash(self, *, success: bool, payload: object) -> None:
        port = self._firmware_port
        target = self._firmware_target
        # The updater never changes the persistent ignored-port preference, so
        # returning the port to BoardManager here is safe.
        self.board_manager.use_port(port)
        self._firmware_busy = False
        self._firmware_port = ""
        self._firmware_target = None
        self.firmware_flash_button.configure(state="normal")
        self.firmware_target_combo.configure(state="readonly")

        if success and target is not None:
            baudrate = getattr(payload, "baudrate", "?")
            self.firmware_status_var.set(
                f"Firmware written and verified on {port} at {baudrate} baud. Reconnecting…"
            )
            self._log(
                f"FIRMWARE UPDATE SUCCESS: {port} {target.label} v{target.firmware_version} ({baudrate} baud)"
            )
            self._scan_boards()
            self.after(1800, lambda: self._verify_firmware_reconnect(port, target, 0))
            return

        detail = str(payload)
        self.firmware_status_var.set(f"Firmware update failed on {port}. The existing controller can be retried.")
        self._log(f"FIRMWARE UPDATE FAILED {port}: {detail}")
        self._scan_boards()
        messagebox.showerror("Firmware update failed", detail)

    def _verify_firmware_reconnect(self, port: str, target: FirmwareTarget, attempt: int) -> None:
        board = self.board_manager.boards_by_port.get(canonical_port(port))
        if board is not None and board.online and board.board_type.upper() == target.board_type:
            reported = board.firmware or target.firmware_version
            self.firmware_status_var.set(
                f"{port} firmware update complete — {target.label} is online and reports v{reported}."
            )
            self._log(f"FIRMWARE RECONNECT OK: {port} {target.board_type} v{reported}")
            return
        if attempt < 2:
            self._scan_boards()
            self.after(1800, lambda: self._verify_firmware_reconnect(port, target, attempt + 1))
            return
        self.firmware_status_var.set(
            f"{port} firmware was written and verified, but the board has not identified yet. "
            "The flash itself succeeded; check the Live Debug tab for the handshake result."
        )
        self._log(f"FIRMWARE RECONNECT PENDING: {port} did not identify after verified flash")

    def _scan_boards(self) -> None:
        if self._firmware_busy:
            self._scan_requested = True
            return
        super()._scan_boards()

    def _auto_rescan(self) -> None:
        if not self._firmware_busy:
            self._scan_boards()
        self.after(5000, self._auto_rescan)

    def _close(self) -> None:
        if self._firmware_busy:
            messagebox.showwarning(
                "Firmware update in progress",
                "Wait for the firmware update to finish before closing OverheadLink.",
            )
            return
        super()._close()


def main() -> None:
    prepare_profile()
    ensure_adirs_required()
    app = FirmwareEnabledOverheadLinkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
