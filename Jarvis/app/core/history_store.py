from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from app.core.models import HistoryEntry


class HistoryStore:
    def __init__(self, history_file: str) -> None:
        self.path = Path(history_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> list[HistoryEntry]:
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return [HistoryEntry(**item) for item in data]

    def append(self, entry: HistoryEntry) -> None:
        entries = self.load()
        entries.append(entry)
        self.save(entries)

    def save(self, entries: Iterable[HistoryEntry]) -> None:
        payload = [
            {
                "timestamp": item.timestamp,
                "role": item.role,
                "text": item.text,
                "intent": item.intent,
                "success": item.success,
            }
            for item in entries
        ]
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
