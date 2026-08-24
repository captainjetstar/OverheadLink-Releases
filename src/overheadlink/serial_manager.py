from __future__ import annotations

from dataclasses import dataclass, field
from queue import Empty, Queue
import threading
from time import monotonic, sleep
from typing import Callable

from .preferences import canonical_port
from .protocol import ProtocolMessage, encode_message, parse_message


try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except ImportError:  # Allows profile/tests to run before pyserial is installed.
    serial = None
    list_ports = None


ARDUINO_VIDS = {0x2341, 0x2A03, 0x1A86, 0x10C4, 0x0403}
MAX_RX_BUFFER = 4096


@dataclass(frozen=True, slots=True)
class PortCandidate:
    device: str
    description: str
    vid: int | None
    pid: int | None


@dataclass(slots=True)
class ConnectedBoard:
    port: str
    board_type: str = "unknown"
    board_uuid: str = ""
    board_name: str = ""
    firmware: str = ""
    last_heartbeat: float = field(default_factory=monotonic)
    connection: "SerialConnection | None" = None

    @property
    def online(self) -> bool:
        return self.connection is not None and self.connection.running and monotonic() - self.last_heartbeat < 4.0

    @property
    def last_error(self) -> str:
        return self.connection.last_error if self.connection is not None else ""


class SerialConnection:
    def __init__(self, port: str, on_message: Callable[[str, ProtocolMessage], None], baudrate: int = 115200):
        if serial is None:
            raise RuntimeError("pyserial is not installed")
        self.port = port
        self.on_message = on_message
        self.baudrate = baudrate
        self._serial = None
        self._thread: threading.Thread | None = None
        self._writes: Queue[bytes] = Queue()
        self._rx = bytearray()
        self.running = False
        self.last_error = ""

    def start(self) -> None:
        if self.running:
            return
        self.last_error = ""
        self._rx.clear()
        self._serial = serial.Serial(self.port, self.baudrate, timeout=0.08, write_timeout=0.5)
        self.running = True
        self._thread = threading.Thread(target=self._run, name=f"OverheadLink-{self.port}", daemon=True)
        self._thread.start()
        # Most Arduino boards reset when the serial port opens.
        sleep(0.25)
        self.send(encode_message("HELLO"))

    def send(self, payload: bytes) -> None:
        if not self.running:
            detail = f": {self.last_error}" if self.last_error else ""
            raise RuntimeError(f"Serial port {self.port} is not running{detail}")
        if not isinstance(payload, (bytes, bytearray)) or not payload:
            raise ValueError("Serial payload must be non-empty bytes")
        self._writes.put(bytes(payload))

    def close(self) -> None:
        self.running = False
        serial_port = self._serial
        if serial_port is not None:
            try:
                serial_port.close()
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=0.75)
        self._thread = None
        self._serial = None
        self._rx.clear()

    def _drain_writes(self) -> None:
        assert self._serial is not None
        while True:
            try:
                payload = self._writes.get_nowait()
            except Empty:
                break
            self._serial.write(payload)

    def _feed_rx(self, chunk: bytes) -> None:
        if not chunk:
            return
        self._rx.extend(chunk)
        if len(self._rx) > MAX_RX_BUFFER:
            # A valid firmware line is tiny. Drop an unbounded/no-newline stream
            # rather than allowing a bad serial device to grow memory forever.
            self._rx.clear()
            self.last_error = "Receive buffer overflow; malformed serial stream discarded"
            return
        while True:
            newline_positions = [position for position in (self._rx.find(b"\n"), self._rx.find(b"\r")) if position >= 0]
            if not newline_positions:
                return
            position = min(newline_positions)
            raw = bytes(self._rx[:position]).strip()
            del self._rx[: position + 1]
            while self._rx[:1] in {b"\n", b"\r"}:
                del self._rx[:1]
            if not raw:
                continue
            try:
                message = parse_message(raw)
            except (ValueError, UnicodeError):
                continue
            self.on_message(self.port, message)

    def _run(self) -> None:
        assert self._serial is not None
        try:
            while self.running:
                self._drain_writes()
                waiting = int(getattr(self._serial, "in_waiting", 0) or 0)
                chunk = self._serial.read(max(1, min(waiting, 256)))
                self._feed_rx(chunk)
        except Exception as error:
            self.last_error = str(error)
            self.running = False
        finally:
            try:
                if self._serial is not None:
                    self._serial.close()
            except Exception:
                pass


class BoardManager:
    def __init__(
        self,
        on_message: Callable[[ConnectedBoard, ProtocolMessage], None] | None = None,
        *,
        ignored_ports: set[str] | None = None,
    ):
        self.on_message = on_message
        self.boards_by_port: dict[str, ConnectedBoard] = {}
        self.last_candidates: dict[str, PortCandidate] = {}
        self.ignored_ports = {canonical_port(port) for port in (ignored_ports or set())}
        self._lock = threading.Lock()

    @property
    def serial_available(self) -> bool:
        return serial is not None and list_ports is not None

    def candidate_ports(self) -> list[PortCandidate]:
        if list_ports is None:
            return []
        candidates: list[PortCandidate] = []
        for port in list_ports.comports():
            description = str(port.description or "")
            lowered = description.lower()
            looks_serial = any(token in lowered for token in ("arduino", "ch340", "usb serial", "cp210", "ftdi"))
            if port.vid in ARDUINO_VIDS or looks_serial:
                candidates.append(PortCandidate(port.device, description, port.vid, port.pid))
        return candidates

    def scan(self) -> list[ConnectedBoard]:
        if not self.serial_available:
            return []
        candidates = {canonical_port(candidate.device): candidate for candidate in self.candidate_ports()}
        self.last_candidates = candidates
        seen = set(candidates) - self.ignored_ports
        with self._lock:
            for port, board in list(self.boards_by_port.items()):
                if port not in seen:
                    if board.connection:
                        board.connection.close()
                    del self.boards_by_port[port]
            for port in sorted(seen):
                existing = self.boards_by_port.get(port)
                if existing and existing.connection and existing.connection.running:
                    continue
                # Preserve the last known identity while a failed serial link is
                # being reopened; it is replaced by the next IDENT packet.
                board = existing or ConnectedBoard(port=port)
                connection = SerialConnection(port, self._handle_message)
                board.connection = connection
                board.last_heartbeat = monotonic()
                self.boards_by_port[port] = board
                try:
                    connection.start()
                except Exception as error:
                    connection.last_error = str(error)
                    connection.close()
        return list(self.boards_by_port.values())

    def ignore_port(self, port: str) -> None:
        normalized = canonical_port(port)
        with self._lock:
            self.ignored_ports.add(normalized)
            board = self.boards_by_port.pop(normalized, None)
            if board and board.connection:
                board.connection.close()

    def use_port(self, port: str) -> None:
        with self._lock:
            self.ignored_ports.discard(canonical_port(port))

    def is_ignored(self, port: str) -> bool:
        return canonical_port(port) in self.ignored_ports

    def _handle_message(self, port: str, message: ProtocolMessage) -> None:
        normalized = canonical_port(port)
        with self._lock:
            board = self.boards_by_port.get(normalized)
            if board is None:
                return
            board.last_heartbeat = monotonic()
            if message.message_type == "IDENT" and len(message.parts) >= 4:
                board.board_type, board.board_uuid, board.board_name, board.firmware = message.parts[:4]
        if self.on_message:
            self.on_message(board, message)

    def by_profile_name(self, name: str) -> ConnectedBoard | None:
        wanted = name.casefold()
        matches = [board for board in self.boards_by_port.values() if board.board_name.casefold() == wanted and board.online]
        return matches[0] if len(matches) == 1 else None

    def duplicate_profile_ports(self, name: str) -> list[str]:
        wanted = name.casefold()
        return sorted(
            board.port
            for board in self.boards_by_port.values()
            if board.board_name.casefold() == wanted and board.online
        )

    def send_to_profile(self, name: str, message_type: str, *parts: object) -> None:
        board = self.by_profile_name(name)
        if board is None or not board.online or board.connection is None:
            duplicates = self.duplicate_profile_ports(name)
            if len(duplicates) > 1:
                raise RuntimeError(f"Board identity {name} is duplicated on {', '.join(duplicates)}")
            raise RuntimeError(f"Board {name} is not online")
        board.connection.send(encode_message(message_type, *parts))

    def stop(self) -> None:
        with self._lock:
            boards = list(self.boards_by_port.values())
            self.boards_by_port.clear()
        for board in boards:
            if board.connection:
                board.connection.close()
