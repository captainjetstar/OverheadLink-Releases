from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import StrEnum
import os
from pathlib import Path
import struct
import sys
import threading
import time
from typing import Callable, Protocol


_DWORD = ctypes.c_uint32


class SimulatorState(StrEnum):
    DISCONNECTED = "disconnected"
    MSFS_CONNECTED = "msfs_connected"
    FENIX_CONNECTED = "fenix_connected"
    ERROR = "error"


@dataclass(slots=True)
class SimulatorStatus:
    state: SimulatorState = SimulatorState.DISCONNECTED
    detail: str = "MSFS 2024 not connected"


class MobiFlightWasmCommandBuilder:
    """Messages understood by the MIT-licensed MobiFlight WASM module."""

    @staticmethod
    def ping() -> str:
        return "MF.Ping"

    @staticmethod
    def version() -> str:
        return "MF.Version.Get"

    @staticmethod
    def execute_rpn(rpn: str) -> str:
        if not rpn or "\x00" in rpn or len(rpn) > 1004:
            raise ValueError("Invalid or overlength RPN command")
        return f"MF.SimVars.Set.{rpn}"

    @staticmethod
    def register_float(expression: str) -> str:
        if not expression or "\x00" in expression or len(expression) > 1004:
            raise ValueError("Invalid or overlength variable expression")
        return f"MF.SimVars.Add.{expression}"


class _ClientDataTransport(Protocol):
    def open(
        self,
        on_data: Callable[[int, bytes], None],
        on_quit: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None: ...

    def map_area(self, name: str, area_id: int) -> None: ...

    def add_definition(self, definition_id: int, offset: int, size: int) -> None: ...

    def request(self, area_id: int, request_id: int, definition_id: int) -> None: ...

    def send(self, area_id: int, definition_id: int, payload: bytes) -> None: ...

    def close(self) -> None: ...


class _SimConnectRecv(ctypes.Structure):
    _fields_ = [
        ("dwSize", _DWORD),
        ("dwVersion", _DWORD),
        ("dwID", _DWORD),
    ]


class _SimConnectRecvClientData(ctypes.Structure):
    _fields_ = [
        ("dwSize", _DWORD),
        ("dwVersion", _DWORD),
        ("dwID", _DWORD),
        ("dwRequestID", _DWORD),
        ("dwObjectID", _DWORD),
        ("dwDefineID", _DWORD),
        ("dwFlags", _DWORD),
        ("dwEntryNumber", _DWORD),
        ("dwOutOf", _DWORD),
        ("dwDefineCount", _DWORD),
        ("dwData", _DWORD),
    ]


class _SimConnectRecvException(ctypes.Structure):
    _fields_ = [
        ("dwSize", _DWORD),
        ("dwVersion", _DWORD),
        ("dwID", _DWORD),
        ("dwException", _DWORD),
        ("dwSendID", _DWORD),
        ("dwIndex", _DWORD),
    ]


class SimConnectClientDataTransport:
    """Small ctypes wrapper for the MSFS Client Data subset used by MobiFlight."""

    RECV_ID_EXCEPTION = 1
    RECV_ID_QUIT = 3
    RECV_ID_CLIENT_DATA = 16
    # SIMCONNECT_CLIENT_DATA_PERIOD_ON_SET is 3. Value 5 is invalid and leaves
    # the MobiFlight.Response request unable to deliver the registration reply.
    PERIOD_ON_SET = 3
    REQUEST_FLAG_CHANGED = 1
    UNUSED = 0xFFFFFFFF

    def __init__(self, dll_path: Path | None = None):
        self.dll_path = dll_path
        self._dll: object | None = None
        self._handle = ctypes.c_void_p()
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._on_data: Callable[[int, bytes], None] = lambda _definition, _payload: None
        self._on_quit: Callable[[], None] = lambda: None
        self._on_error: Callable[[str], None] = lambda _detail: None

    def open(
        self,
        on_data: Callable[[int, bytes], None],
        on_quit: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        if os.name != "nt":
            raise OSError("Live SimConnect is Windows-only")
        self._on_data = on_data
        self._on_quit = on_quit
        self._on_error = on_error
        self._dll = self._load_dll()
        self._configure_api()
        self._call("SimConnect_Open", ctypes.byref(self._handle), b"OverheadLink", None, 0, None, 0)
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._dispatch_loop, name="OverheadLink-SimConnect", daemon=True)
        self._thread.start()

    def map_area(self, name: str, area_id: int) -> None:
        self._call("SimConnect_MapClientDataNameToID", self._handle, name.encode("ascii"), area_id)

    def add_definition(self, definition_id: int, offset: int, size: int) -> None:
        self._call(
            "SimConnect_AddToClientDataDefinition",
            self._handle,
            definition_id,
            offset,
            size,
            ctypes.c_float(0.0),
            self.UNUSED,
        )

    def request(self, area_id: int, request_id: int, definition_id: int) -> None:
        self._call(
            "SimConnect_RequestClientData",
            self._handle,
            area_id,
            request_id,
            definition_id,
            self.PERIOD_ON_SET,
            self.REQUEST_FLAG_CHANGED,
            0,
            0,
            0,
        )

    def send(self, area_id: int, definition_id: int, payload: bytes) -> None:
        buffer = ctypes.create_string_buffer(payload, len(payload))
        self._call(
            "SimConnect_SetClientData",
            self._handle,
            area_id,
            definition_id,
            0,
            0,
            len(payload),
            ctypes.cast(buffer, ctypes.c_void_p),
        )

    def close(self) -> None:
        self._running = False
        self._stop_event.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        if self._dll is not None and self._handle.value:
            try:
                self._call("SimConnect_Close", self._handle)
            except OSError:
                pass
        self._handle = ctypes.c_void_p()

    def _load_dll(self) -> object:
        loader = getattr(ctypes, "WinDLL")
        errors: list[str] = []
        for candidate in self.dll_candidates(self.dll_path):
            directory_handles: list[object] = []
            try:
                add_directory = getattr(os, "add_dll_directory", None)
                if add_directory is not None:
                    for directory in (candidate.parent, Path(sys.executable).resolve().parent):
                        if directory.is_dir():
                            directory_handles.append(add_directory(str(directory)))
                # Search the selected DLL's own folder for dependencies, then
                # the standard Windows runtime locations.
                return loader(str(candidate), winmode=0x00001100)
            except OSError as error:
                errors.append(f"{candidate}: {error}")
            finally:
                for handle in directory_handles:
                    try:
                        handle.close()
                    except OSError:
                        pass
        try:
            return loader("SimConnect.dll")
        except OSError as error:
            errors.append(f"Windows loader: {error}")
        raise OSError(
            "SimConnect could not start. The bundled runtime and installed MSFS/MobiFlight copies were checked. "
            + " | ".join(errors)
        )

    @staticmethod
    def dll_candidates(explicit: Path | None = None) -> list[Path]:
        candidates: list[Path] = []
        if explicit is not None:
            candidates.append(explicit)
        configured = os.environ.get("OVERHEADLINK_SIMCONNECT_DLL")
        if configured:
            candidates.append(Path(configured))
        application_root = Path(getattr(sys, "_MEIPASS")) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parents[2]
        executable_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                application_root / "vendor" / "SimConnect.dll",
                application_root / "SimConnect.dll",
                executable_dir / "SimConnect.dll",
                Path.cwd() / "SimConnect.dll",
            ]
        )
        for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "APPDATA"):
            value = os.environ.get(variable)
            if not value:
                continue
            root = Path(value)
            candidates.extend(
                [
                    root / "MobiFlight" / "MobiFlight Connector" / "SimConnect.dll",
                    root / "MobiFlight" / "SimConnect.dll",
                    root / "MobiFlight Connector" / "SimConnect.dll",
                ]
            )
        sdk = os.environ.get("MSFS2024_SDK")
        if sdk:
            sdk_path = Path(sdk)
            candidates.extend(
                [
                    sdk_path / "SimConnect SDK" / "lib" / "SimConnect.dll",
                    sdk_path / "SimConnect SDK" / "lib" / "static" / "SimConnect.dll",
                    sdk_path / "lib" / "SimConnect.dll",
                ]
            )
        unique: list[Path] = []
        for candidate in candidates:
            if candidate not in unique and candidate.is_file():
                unique.append(candidate)
        return unique

    def _configure_api(self) -> None:
        assert self._dll is not None
        api = self._dll
        api.SimConnect_Open.restype = ctypes.c_long
        api.SimConnect_Open.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_char_p,
            ctypes.c_void_p,
            _DWORD,
            ctypes.c_void_p,
            _DWORD,
        ]
        api.SimConnect_Close.restype = ctypes.c_long
        api.SimConnect_Close.argtypes = [ctypes.c_void_p]
        api.SimConnect_MapClientDataNameToID.restype = ctypes.c_long
        api.SimConnect_MapClientDataNameToID.argtypes = [ctypes.c_void_p, ctypes.c_char_p, _DWORD]
        api.SimConnect_AddToClientDataDefinition.restype = ctypes.c_long
        api.SimConnect_AddToClientDataDefinition.argtypes = [
            ctypes.c_void_p,
            _DWORD,
            _DWORD,
            _DWORD,
            ctypes.c_float,
            _DWORD,
        ]
        api.SimConnect_RequestClientData.restype = ctypes.c_long
        api.SimConnect_RequestClientData.argtypes = [ctypes.c_void_p] + [_DWORD] * 8
        api.SimConnect_SetClientData.restype = ctypes.c_long
        api.SimConnect_SetClientData.argtypes = [ctypes.c_void_p] + [_DWORD] * 5 + [ctypes.c_void_p]
        api.SimConnect_GetNextDispatch.restype = ctypes.c_long
        api.SimConnect_GetNextDispatch.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.POINTER(_SimConnectRecv)),
            ctypes.POINTER(_DWORD),
        ]

    def _call(self, name: str, *args: object) -> None:
        if self._dll is None:
            raise OSError("SimConnect transport is not open")
        with self._lock:
            result = int(getattr(self._dll, name)(*args))
        if result != 0:
            raise OSError(f"{name} failed with HRESULT 0x{result & 0xFFFFFFFF:08X}")

    def _next_packet(self) -> bytes | None:
        if self._dll is None:
            return None
        pointer = ctypes.POINTER(_SimConnectRecv)()
        size = _DWORD()
        with self._lock:
            result = int(self._dll.SimConnect_GetNextDispatch(self._handle, ctypes.byref(pointer), ctypes.byref(size)))
        if result != 0 or not pointer or size.value < ctypes.sizeof(_SimConnectRecv):
            return None
        return ctypes.string_at(pointer, size.value)

    def _dispatch_loop(self) -> None:
        try:
            while self._running:
                packet = self._next_packet()
                if packet is None:
                    self._stop_event.wait(0.01)
                    continue
                self._dispatch_packet(packet)
        except Exception as error:
            if self._running:
                self._on_error(f"SimConnect dispatch stopped: {error}")
        finally:
            self._running = False

    def _dispatch_packet(self, packet: bytes) -> None:
        base = _SimConnectRecv.from_buffer_copy(packet)
        if base.dwID == self.RECV_ID_QUIT:
            self._on_quit()
            return
        if base.dwID == self.RECV_ID_EXCEPTION:
            if len(packet) >= ctypes.sizeof(_SimConnectRecvException):
                exception = _SimConnectRecvException.from_buffer_copy(packet)
                self._on_error(
                    "MSFS reported SimConnect exception "
                    f"{int(exception.dwException)} (send {int(exception.dwSendID)}, index {int(exception.dwIndex)})"
                )
            else:
                self._on_error("MSFS reported a SimConnect exception")
            return
        if base.dwID != self.RECV_ID_CLIENT_DATA or len(packet) < ctypes.sizeof(_SimConnectRecvClientData):
            return
        header = _SimConnectRecvClientData.from_buffer_copy(packet)
        offset = _SimConnectRecvClientData.dwData.offset
        self._on_data(int(header.dwDefineID), packet[offset:])


class FenixBridge:
    """MSFS 2024 SimConnect + MobiFlight-WASM transport for Fenix RPN/LVars."""

    STRING_SIZE = 1024
    DEFAULT_LVARS = 0
    DEFAULT_COMMAND = 1
    DEFAULT_RESPONSE = 2
    PRIVATE_LVARS = 3
    PRIVATE_COMMAND = 4
    PRIVATE_RESPONSE = 5
    DEFAULT_STRING_DEFINITION = 0
    PRIVATE_STRING_DEFINITION = 1
    VARIABLE_DEFINITION_START = 1000
    CLIENT_NAME = "OverheadLink"

    def __init__(
        self,
        on_feedback: Callable[[str, float], None] | None = None,
        *,
        transport_factory: Callable[[], _ClientDataTransport] | None = None,
        registration_timeout: float = 8.0,
    ):
        self.on_feedback = on_feedback
        self.status = SimulatorStatus()
        self._transport_factory = transport_factory or SimConnectClientDataTransport
        self._transport: _ClientDataTransport | None = None
        self._registration_timeout = registration_timeout
        self._ready = threading.Event()
        self._wasm_seen = threading.Event()
        self._transport_failed = threading.Event()
        self._definition_to_assignments: dict[int, list[str]] = {}
        self._expression_to_definition: dict[str, int] = {}
        self._lock = threading.RLock()

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def connect(self) -> SimulatorStatus:
        self.close()
        self._wasm_seen.clear()
        self._transport_failed.clear()
        if os.name != "nt" and self._transport_factory is SimConnectClientDataTransport:
            self.status = SimulatorStatus(SimulatorState.DISCONNECTED, "Live SimConnect is Windows-only")
            return self.status
        try:
            self._transport = self._transport_factory()
            self._transport.open(self._on_client_data, self._on_quit, self._on_transport_error)
            self._initialize_client(
                "MobiFlight",
                self.DEFAULT_LVARS,
                self.DEFAULT_COMMAND,
                self.DEFAULT_RESPONSE,
                self.DEFAULT_STRING_DEFINITION,
            )
            self.status = SimulatorStatus(SimulatorState.MSFS_CONNECTED, "MSFS 2024 connected; waiting for MobiFlight WASM")
            # The WASM module can ignore the first command after a new client starts.
            # Ping first, then retry registration while MSFS finishes loading the module.
            self._send_command(MobiFlightWasmCommandBuilder.ping(), self.DEFAULT_COMMAND, self.DEFAULT_STRING_DEFINITION)
            deadline = time.monotonic() + self._registration_timeout
            while not self.ready and not self._transport_failed.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._send_command(
                    f"MF.Clients.Add.{self.CLIENT_NAME}",
                    self.DEFAULT_COMMAND,
                    self.DEFAULT_STRING_DEFINITION,
                )
                self._ready.wait(min(1.0, remaining))
            if self.ready:
                self.status = SimulatorStatus(SimulatorState.FENIX_CONNECTED, "MSFS 2024 + Fenix WASM bridge ready")
            elif self._transport_failed.is_set():
                # The callback already supplied the exact SimConnect error.
                pass
            else:
                detail = (
                    "MobiFlight WASM answered, but client registration did not finish; click Connect to retry"
                    if self._wasm_seen.is_set()
                    else "MSFS 2024 connected, but no MobiFlight WASM response was received; click Connect to retry"
                )
                self.status = SimulatorStatus(
                    SimulatorState.MSFS_CONNECTED,
                    detail,
                )
        except Exception as error:
            self.close()
            self.status = SimulatorStatus(SimulatorState.ERROR, str(error))
        return self.status

    def execute(self, rpn: str) -> None:
        if not self.ready:
            raise RuntimeError("Fenix WASM bridge is not ready")
        self._send_command(
            MobiFlightWasmCommandBuilder.execute_rpn(rpn),
            self.PRIVATE_COMMAND,
            self.PRIVATE_STRING_DEFINITION,
        )

    def subscribe(self, assignment_id: str, expression: str) -> None:
        if not self.ready or self._transport is None:
            raise RuntimeError("Fenix WASM bridge is not ready")
        with self._lock:
            existing = self._expression_to_definition.get(expression)
            if existing is not None:
                if assignment_id not in self._definition_to_assignments[existing]:
                    self._definition_to_assignments[existing].append(assignment_id)
                return
            index = len(self._expression_to_definition)
            definition_id = self.VARIABLE_DEFINITION_START + index
            offset = index * 4
            self._transport.add_definition(definition_id, offset, 4)
            self._transport.request(self.PRIVATE_LVARS, definition_id, definition_id)
            self._expression_to_definition[expression] = definition_id
            self._definition_to_assignments[definition_id] = [assignment_id]
            self._send_command(
                MobiFlightWasmCommandBuilder.register_float(expression),
                self.PRIVATE_COMMAND,
                self.PRIVATE_STRING_DEFINITION,
            )

    def close(self) -> None:
        transport = self._transport
        self._transport = None
        self._ready.clear()
        self._wasm_seen.clear()
        self._transport_failed.clear()
        self._definition_to_assignments.clear()
        self._expression_to_definition.clear()
        if transport is not None:
            transport.close()
        self.status = SimulatorStatus()

    def _initialize_client(self, name: str, lvars: int, command: int, response: int, definition: int) -> None:
        if self._transport is None:
            raise RuntimeError("SimConnect transport is not open")
        self._transport.map_area(f"{name}.LVars", lvars)
        self._transport.map_area(f"{name}.Command", command)
        self._transport.map_area(f"{name}.Response", response)
        self._transport.add_definition(definition, 0, self.STRING_SIZE)
        self._transport.request(response, definition, definition)

    def _send_command(self, command: str, command_area: int, definition: int) -> None:
        if self._transport is None:
            raise RuntimeError("SimConnect transport is not open")
        encoded = command.encode("ascii")
        if len(encoded) >= self.STRING_SIZE or b"\x00" in encoded:
            raise ValueError("MobiFlight command is too long or contains NUL")
        self._transport.send(command_area, definition, encoded.ljust(self.STRING_SIZE, b"\x00"))

    def _on_client_data(self, definition_id: int, payload: bytes) -> None:
        if definition_id == self.DEFAULT_STRING_DEFINITION:
            response = payload.split(b"\x00", 1)[0].decode("ascii", errors="replace")
            if response:
                self._wasm_seen.set()
            if response == f"MF.Clients.Add.{self.CLIENT_NAME}.Finished" and not self.ready:
                try:
                    self._initialize_client(
                        self.CLIENT_NAME,
                        self.PRIVATE_LVARS,
                        self.PRIVATE_COMMAND,
                        self.PRIVATE_RESPONSE,
                        self.PRIVATE_STRING_DEFINITION,
                    )
                    self._send_command("OverheadLink.Ready", self.PRIVATE_COMMAND, self.PRIVATE_STRING_DEFINITION)
                    self._send_command(MobiFlightWasmCommandBuilder.version(), self.PRIVATE_COMMAND, self.PRIVATE_STRING_DEFINITION)
                    self._ready.set()
                    self.status = SimulatorStatus(SimulatorState.FENIX_CONNECTED, "MSFS 2024 + Fenix WASM bridge ready")
                except Exception as error:
                    self._on_transport_error(f"Could not initialize private WASM channels: {error}")
            return
        assignments = self._definition_to_assignments.get(definition_id)
        if assignments and len(payload) >= 4:
            value = float(struct.unpack_from("<f", payload)[0])
            for assignment_id in tuple(assignments):
                if self.on_feedback:
                    self.on_feedback(assignment_id, value)

    def _on_quit(self) -> None:
        self._ready.clear()
        self.status = SimulatorStatus(SimulatorState.DISCONNECTED, "MSFS 2024 closed")

    def _on_transport_error(self, detail: str) -> None:
        self._ready.clear()
        self._transport_failed.set()
        self.status = SimulatorStatus(SimulatorState.ERROR, detail)


class MockFenixBridge(FenixBridge):
    def __init__(self, on_feedback: Callable[[str, float], None] | None = None):
        super().__init__(on_feedback)
        self.commands: list[str] = []
        self.subscriptions: dict[str, str] = {}

    @property
    def ready(self) -> bool:
        return True

    def connect(self) -> SimulatorStatus:
        self.status = SimulatorStatus(SimulatorState.FENIX_CONNECTED, "Offline Fenix simulator enabled")
        return self.status

    def execute(self, rpn: str) -> None:
        self.commands.append(MobiFlightWasmCommandBuilder.execute_rpn(rpn))

    def subscribe(self, assignment_id: str, expression: str) -> None:
        self.subscriptions[assignment_id] = MobiFlightWasmCommandBuilder.register_float(expression)

    def close(self) -> None:
        self.commands.clear()
        self.subscriptions.clear()
        self.status = SimulatorStatus()

    def publish(self, assignment_id: str, value: float) -> None:
        if self.on_feedback:
            self.on_feedback(assignment_id, value)
