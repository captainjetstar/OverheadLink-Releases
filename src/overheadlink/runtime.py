from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox
from typing import Any

from .app import OverheadLinkApp
from .bootstrap import prepare_profile
from .models import PeripheralType
from .preferences import canonical_port
from .remote import RemotePanelServer, install_remote_tab
from .simulator import SimulatorState


PERIPHERAL_FEEDBACK_PREFIX = "@peripheral:"


def version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.strip().lstrip("vV").split("."))
    except ValueError:
        return ()


class EnhancedOverheadLinkApp(OverheadLinkApp):
    """Reliability layer for v0.3.8.

    The original UI remains deliberately stable while hardware peripherals and
    flight-critical error handling are isolated here. This keeps the update
    small and reversible while removing the v0.3.7 bootstrap monkey-patches.
    """

    def __init__(self) -> None:
        self._peripheral_bridge_token: int | None = None
        self._peripheral_values: dict[str, float] = {}
        self._display_dash_sent: set[str] = set()
        self.remote_panel_server: RemotePanelServer | None = None
        super().__init__()
        try:
            self.remote_panel_server = RemotePanelServer(self)
            self.remote_panel_server.start()
            install_remote_tab(self, self.remote_panel_server)
            self._log(
                f"REMOTE PANEL ready: {self.remote_panel_server.url} | pairing code {self.remote_panel_server.pairing_code}"
            )
        except Exception as error:
            self.remote_panel_server = None
            self._log(f"REMOTE PANEL unavailable: {error}")

    def _auto_runtime_tick(self) -> None:
        # v0.3.7 only retried DISCONNECTED/ERROR. A registration timeout leaves
        # the bridge in MSFS_CONNECTED, which could permanently stop retries.
        if not self.offline_fenix.get() and not self.fenix_connecting and not self.fenix.ready:
            self._dash_all_displays()
            self._begin_fenix_connect(force=True)
        self.after(15000, self._auto_runtime_tick)

    def _subscribe_profile_feedback(self) -> None:
        super()._subscribe_profile_feedback()
        if not self.fenix.ready:
            return
        bridge_token = id(self.fenix)
        if self._peripheral_bridge_token == bridge_token:
            return
        subscribed = 0
        for board in self.profile.boards:
            for peripheral in board.peripherals:
                if not peripheral.sim_expression:
                    continue
                feedback_id = self._peripheral_feedback_id(board.id, peripheral.id)
                try:
                    self.fenix.subscribe(feedback_id, peripheral.sim_expression)
                    subscribed += 1
                except (RuntimeError, ValueError) as error:
                    self._log(f"PERIPHERAL SUBSCRIBE BLOCKED {peripheral.id}: {error}")
        self._peripheral_bridge_token = bridge_token
        if subscribed:
            self._log(f"Peripheral feedback subscriptions: {subscribed}")

    def _process_fenix_feedback(self, assignment_id: str, value: float) -> None:
        if assignment_id.startswith(PERIPHERAL_FEEDBACK_PREFIX):
            self._process_peripheral_feedback(assignment_id, value)
            return
        super()._process_fenix_feedback(assignment_id, value)

    @staticmethod
    def _peripheral_feedback_id(board_id: str, peripheral_id: str) -> str:
        return f"{PERIPHERAL_FEEDBACK_PREFIX}{board_id}:{peripheral_id}"

    def _find_peripheral(self, feedback_id: str) -> tuple[Any, Any] | None:
        body = feedback_id[len(PERIPHERAL_FEEDBACK_PREFIX) :]
        if ":" not in body:
            return None
        board_id, peripheral_id = body.split(":", 1)
        board = self.profile.board(board_id)
        peripheral = board.peripheral(peripheral_id) if board else None
        return (board, peripheral) if board is not None and peripheral is not None else None

    def _process_peripheral_feedback(self, feedback_id: str, value: float) -> None:
        found = self._find_peripheral(feedback_id)
        if found is None:
            self._log(f"PERIPHERAL FEEDBACK unknown {feedback_id} = {value}")
            return
        board, peripheral = found
        if not math.isfinite(value):
            self._send_display_dash(board, peripheral)
            return
        self._peripheral_values[feedback_id] = value
        if peripheral.peripheral_type != PeripheralType.TM1637_4DIGIT:
            return
        if not peripheral.minimum_value <= value <= peripheral.maximum_value:
            self._send_display_dash(board, peripheral)
            self._log(f"BAT2 DISPLAY source outside plausible range: {value:.3f}")
            return
        connected = self.board_manager.by_profile_name(board.name)
        if connected is None or not connected.online or connected.connection is None:
            return
        tenths = int(round(value * 10.0))
        try:
            connected.connection.send(self._message("TM1637_VALUE", tenths))
            self._display_dash_sent.discard(feedback_id)
            self._log(f"TM1637 {board.name} {peripheral.name}: {value:.1f} V")
        except RuntimeError as error:
            self._log(f"TM1637 SEND FAILED {peripheral.id}: {error}")

    def _configure_board(self, board_id: str, *, show_warnings: bool) -> bool:
        loaded = super()._configure_board(board_id, show_warnings=show_warnings)
        if not loaded:
            return False
        board = self.profile.board(board_id)
        connected = self.board_manager.by_profile_name(board.name) if board else None
        if board is None or connected is None or connected.connection is None:
            return loaded
        for peripheral in board.peripherals:
            if peripheral.peripheral_type != PeripheralType.TM1637_4DIGIT:
                continue
            if version_tuple(connected.firmware) < (0, 3, 0):
                detail = (
                    f"{board.name} firmware {connected.firmware or 'unknown'} does not support the TM1637 driver. "
                    "Flash OverheadLinkMega firmware v0.3.0 or newer."
                )
                self._log(f"TM1637 DRIVER UNAVAILABLE: {detail}")
                if show_warnings:
                    messagebox.showwarning("TM1637 firmware update required", detail)
                continue
            pins = peripheral.numeric_pins
            try:
                connected.connection.send(
                    self._message("TM1637_CFG", pins["clk"], pins["dio"], peripheral.brightness)
                )
                feedback_id = self._peripheral_feedback_id(board.id, peripheral.id)
                value = self._peripheral_values.get(feedback_id)
                if value is not None and math.isfinite(value) and peripheral.minimum_value <= value <= peripheral.maximum_value:
                    connected.connection.send(self._message("TM1637_VALUE", int(round(value * 10.0))))
                else:
                    connected.connection.send(self._message("TM1637_DASH"))
                self._log(
                    f"TM1637 configured: {board.name} CLK={peripheral.pins['clk']} DIO={peripheral.pins['dio']}"
                )
            except (KeyError, RuntimeError) as error:
                self._log(f"TM1637 CONFIG FAILED {peripheral.id}: {error}")
                if show_warnings:
                    messagebox.showerror("TM1637 configuration", str(error))
        return loaded

    def _send_display_dash(self, board: Any, peripheral: Any) -> None:
        feedback_id = self._peripheral_feedback_id(board.id, peripheral.id)
        if feedback_id in self._display_dash_sent:
            return
        connected = self.board_manager.by_profile_name(board.name)
        if connected is None or not connected.online or connected.connection is None:
            return
        try:
            connected.connection.send(self._message("TM1637_DASH"))
            self._display_dash_sent.add(feedback_id)
        except RuntimeError:
            pass

    def _dash_all_displays(self) -> None:
        for board in self.profile.boards:
            for peripheral in board.peripherals:
                if peripheral.peripheral_type == PeripheralType.TM1637_4DIGIT:
                    self._send_display_dash(board, peripheral)

    def _assign_port_identity(self, port: str, name: str) -> None:
        other_ports = [
            candidate
            for candidate in self.board_manager.duplicate_profile_ports(name)
            if canonical_port(candidate) != canonical_port(port)
        ]
        if other_ports:
            messagebox.showwarning(
                "Panel identity already in use",
                f"{name} is already online on {', '.join(other_ports)}.\n\n"
                "Each panel identity must belong to exactly one online controller. Disconnect or reassign the other board first.",
            )
            return
        super()._assign_port_identity(port, name)

    def _handle_board_message(self, board: Any, message: Any) -> None:
        try:
            super()._handle_board_message(board, message)
        except (ValueError, TypeError, IndexError) as error:
            self._log(f"INVALID BOARD MESSAGE {board.port} {message.raw!r}: {error}")
            return
        if message.message_type == "ERR":
            self._log(f"FIRMWARE ERROR {board.port}: {' '.join(message.parts)}")

    def _stop_learning_modes(self) -> None:
        for connected in list(self.board_manager.boards_by_port.values()):
            if connected.online and connected.connection:
                try:
                    connected.connection.send(self._message("LEARN_IN", 0))
                    connected.connection.send(self._message("LEARN_ANALOG", 0))
                except RuntimeError:
                    pass

    def _complete_repair(self, result: Any) -> None:
        try:
            super()._complete_repair(result)
        except (KeyError, ValueError, OSError, RuntimeError) as error:
            self._log(f"PIN REPAIR FAILED: {error}")
            self.learning_status.configure(text=f"Pin correction was not saved: {error}")
            messagebox.showerror("Pin correction not saved", str(error))
            self.learning = None
            self.repair_target = None
        finally:
            self._stop_learning_modes()

    def _complete_analog_repair(self, result: Any) -> None:
        try:
            super()._complete_analog_repair(result)
        except (KeyError, ValueError, OSError, RuntimeError) as error:
            self._log(f"ANALOG REPAIR FAILED: {error}")
            self.learning_status.configure(text=f"Analogue correction was not saved: {error}")
            messagebox.showerror("Analogue correction not saved", str(error))
            self.analog_learning = None
            self.repair_target = None
        finally:
            self._stop_learning_modes()

    def _save_brightness(self) -> None:
        try:
            super()._save_brightness()
        except (tk.TclError, ValueError, OSError) as error:
            self._log(f"BACKLIGHT SAVE FAILED: {error}")
            messagebox.showerror("Brightness", f"The brightness settings could not be saved:\n{error}")

    def _close(self) -> None:
        server = self.remote_panel_server
        self.remote_panel_server = None
        if server is not None:
            try:
                server.stop()
            except Exception as error:
                self._log(f"REMOTE PANEL shutdown warning: {error}")
        super()._close()


def main() -> None:
    prepare_profile()
    app = EnhancedOverheadLinkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
