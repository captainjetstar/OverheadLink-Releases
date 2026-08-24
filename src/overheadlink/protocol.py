from __future__ import annotations

from dataclasses import dataclass


PROTOCOL_PREFIX = "OL1"


def checksum(body: str) -> int:
    value = 0
    for byte in body.encode("ascii", errors="strict"):
        value ^= byte
    return value


def encode_message(message_type: str, *parts: object) -> bytes:
    fields = [PROTOCOL_PREFIX, message_type.upper(), *(str(part) for part in parts)]
    body = "|".join(fields)
    return f"{body}|{checksum(body):02X}\n".encode("ascii")


@dataclass(frozen=True, slots=True)
class ProtocolMessage:
    message_type: str
    parts: tuple[str, ...]
    raw: str


def parse_message(line: str | bytes) -> ProtocolMessage:
    if isinstance(line, bytes):
        line = line.decode("ascii", errors="strict")
    line = line.strip()
    fields = line.split("|")
    if len(fields) < 3 or fields[0] != PROTOCOL_PREFIX:
        raise ValueError("Not an OverheadLink protocol message")
    supplied = int(fields[-1], 16)
    body = "|".join(fields[:-1])
    expected = checksum(body)
    if supplied != expected:
        raise ValueError(f"Checksum mismatch: got {supplied:02X}, expected {expected:02X}")
    return ProtocolMessage(fields[1].upper(), tuple(fields[2:-1]), line)

