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
        self.running = False

    def start(self) -> None:
        if self.running:
            return
        self._serial = serial.Serial(self.port, self.baudrate, timeout=0.15, write_timeout=0.5)
        self.running = True
        self._thread = threading.Thread(target=self._run, name=f"OverheadLink-{self.port}", daemon=True)
        self._thread.start()
        # Most Arduino boards reset when the serial port opens.
        sleep(0.25)
        self.send(encode_message("HELLO"))

    def send(self, payload: bytes) -> None:
        if not self.running:
            raise RuntimeError(f"Serial port {self.port} is not running")
        self._writes.put(payload)

    def close(self) -> None:
        self.running = False
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass

    def _run(self) -> None:
        assert self._serial is not None
        try:
            while self.running:
                try:
                    while True:
                        self._serial.write(self._writes.get_nowait())
                except Empty:
                    pass
                raw = self._serial.readline()
                if not raw:
                    continue
                try:
                    message = parse_message(raw)
                except (ValueError, UnicodeError):
                    continue
                self.on_message(self.port, message)
        except Exception:
            self.running = False
        finally:
            try:
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
                board = ConnectedBoard(port=port)
                connection = SerialConnection(port, self._handle_message)
                board.connection = connection
                self.boards_by_port[port] = board
                try:
                    connection.start()
                except Exception:
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
        with self._lock:
            board = self.boards_by_port.get(port)
            if board is None:
                return
            board.last_heartbeat = monotonic()
            if message.message_type == "IDENT" and len(message.parts) >= 4:
                board.board_type, board.board_uuid, board.board_name, board.firmware = message.parts[:4]
        if self.on_message:
            self.on_message(board, message)

    def by_profile_name(self, name: str) -> ConnectedBoard | None:
        wanted = name.casefold()
        return next((board for board in self.boards_by_port.values() if board.board_name.casefold() == wanted), None)

    def send_to_profile(self, name: str, message_type: str, *parts: object) -> None:
        board = self.by_profile_name(name)
        if board is None or not board.online or board.connection is None:
            raise RuntimeError(f"Board {name} is not online")
        board.connection.send(encode_message(message_type, *parts))

    def stop(self) -> None:
        with self._lock:
            for board in self.boards_by_port.values():
                if board.connection:
                    board.connection.close()
