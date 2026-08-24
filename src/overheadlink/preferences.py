from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


def canonical_port(port: str) -> str:
    value = str(port).strip()
    return value.upper() if value.casefold().startswith("com") else value


@dataclass(slots=True)
class AppPreferences:
    path: Path
    ignored_ports: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> "AppPreferences":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            values = payload.get("ignoredPorts", []) if isinstance(payload, dict) else []
            ignored = {canonical_port(value) for value in values if isinstance(value, str) and value.strip()}
        except (OSError, json.JSONDecodeError):
            ignored = set()
        return cls(path=path, ignored_ports=ignored)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {
            "schemaVersion": 1,
            "ignoredPorts": sorted(self.ignored_ports, key=str.casefold),
        }
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def ignore(self, port: str) -> None:
        self.ignored_ports.add(canonical_port(port))
        self.save()

    def use(self, port: str) -> None:
        self.ignored_ports.discard(canonical_port(port))
        self.save()
