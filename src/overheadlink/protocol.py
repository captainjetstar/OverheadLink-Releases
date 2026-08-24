from __future__ import annotations

from dataclasses import dataclass
import string


PROTOCOL_PREFIX = "OL1"
MAX_MESSAGE_LENGTH = 4096


def checksum(body: str) -> int:
    value = 0
    for byte in body.encode("ascii", errors="strict"):
        value ^= byte
    return value


def encode_message(message_type: str, *parts: object) -> bytes:
    message_type = str(message_type).strip().upper()
    if not message_type or any(character in message_type for character in "|\r\n\x00"):
        raise ValueError("Invalid protocol message type")
    rendered: list[str] = []
    for part in parts:
        value = str(part)
        if any(character in value for character in "|\r\n\x00"):
            raise ValueError("Protocol fields cannot contain separators, newlines or NUL")
        rendered.append(value)
    fields = [PROTOCOL_PREFIX, message_type, *rendered]
    body = "|".join(fields)
    if len(body) > MAX_MESSAGE_LENGTH:
        raise ValueError("Protocol message is too long")
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
    if not line or len(line) > MAX_MESSAGE_LENGTH:
        raise ValueError("Invalid OverheadLink message length")
    fields = line.split("|")
    if len(fields) < 3 or fields[0] != PROTOCOL_PREFIX:
        raise ValueError("Not an OverheadLink protocol message")
    checksum_text = fields[-1]
    if len(checksum_text) != 2 or any(character not in string.hexdigits for character in checksum_text):
        raise ValueError("Invalid checksum field")
    supplied = int(checksum_text, 16)
    body = "|".join(fields[:-1])
    expected = checksum(body)
    if supplied != expected:
        raise ValueError(f"Checksum mismatch: got {supplied:02X}, expected {expected:02X}")
    message_type = fields[1].strip().upper()
    if not message_type:
        raise ValueError("Missing protocol message type")
    return ProtocolMessage(message_type, tuple(fields[2:-1]), line)
