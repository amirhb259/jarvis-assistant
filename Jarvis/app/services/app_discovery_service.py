from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

from app.core.models import AppConfig, AppIndexEntry, AppMatch


EventSink = Callable[[str], None]


class AppDiscoveryService:
    def __init__(self, config: AppConfig, logger) -> None:
        self.config = config
        self.logger = logger
        self.cache_path = Path(config.app_index_file)
        self.entries: list[AppIndexEntry] = []
        self.metadata: dict[str, object] = {}
        self.load_cache()

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        self.cache_path = Path(config.app_index_file)

    def load_cache(self) -> bool:
        if not self.cache_path.exists():
            self.entries = []
            self.metadata = {}
            return False

        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            self.entries = [AppIndexEntry.from_dict(item) for item in payload.get("entries", [])]
            self.metadata = dict(payload.get("metadata", {}))
            return True
        except Exception:
            self.logger.exception("Failed to load app index cache")
            self.entries = []
            self.metadata = {}
            return False

    def refresh_index(self, emit: EventSink | None = None) -> dict[str, object]:
        self._emit(emit, "Refreshing installed app index")
        discovered: dict[str, AppIndexEntry] = {}

        for label, directory in self._shortcut_directories():
            self._scan_directory(
                directory=directory,
                discovered=discovered,
                source=label,
                allowed_suffixes={".lnk", ".url"},
                max_depth=6,
            )

        for label, directory in self._executable_directories():
            self._scan_directory(
                directory=directory,
                discovered=discovered,
                source=label,
                allowed_suffixes={".exe"},
                max_depth=int(self.config.app_discovery_max_depth),
            )

        self.entries = sorted(discovered.values(), key=lambda entry: (entry.name.lower(), entry.source, entry.launch_target))
        self.metadata = {
            "count": len(self.entries),
            "indexed_at": self._timestamp(),
            "sources": sorted({entry.source for entry in self.entries}),
        }
        self._save_cache()
        self._emit(emit, f"Indexed {len(self.entries)} launchable apps")
        self.logger.info("App index refreshed with %s entries", len(self.entries))
        return self.metadata

    def search(self, query: str, limit: int = 5) -> list[AppMatch]:
        normalized_query = self._normalize(query)
        if not normalized_query:
            return []

        matches: list[AppMatch] = []
        for entry in self.entries:
            score, reason = self._score_entry(entry, normalized_query)
            if score <= 0:
                continue
            matches.append(AppMatch(entry=entry, score=score, match_reason=reason))

        matches.sort(key=lambda item: (item.score, self._source_priority(item.entry.source), -len(item.entry.name)), reverse=True)
        return matches[:limit]

    def suggestions(self, query: str, limit: int = 5) -> list[str]:
        seen: set[str] = set()
        names: list[str] = []
        for match in self.search(query, limit=limit * 2):
            label = match.entry.name
            lowered = label.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            names.append(label)
            if len(names) >= limit:
                break
        return names

    def get_summary(self) -> dict[str, object]:
        return {
            "count": int(self.metadata.get("count", len(self.entries))),
            "indexed_at": str(self.metadata.get("indexed_at", "Never")),
            "sources": list(self.metadata.get("sources", [])),
        }

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadata": self.metadata,
            "entries": [entry.to_dict() for entry in self.entries],
        }
        self.cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _scan_directory(
        self,
        directory: Path,
        discovered: dict[str, AppIndexEntry],
        source: str,
        allowed_suffixes: set[str],
        max_depth: int,
    ) -> None:
        try:
            directory = directory.expanduser()
        except Exception:
            return

        if not directory.exists():
            return

        base_depth = len(directory.parts)
        for root, dirs, files in os.walk(directory, topdown=True):
            current = Path(root)
            depth = len(current.parts) - base_depth
            if depth >= max_depth:
                dirs[:] = []
            else:
                dirs[:] = [item for item in dirs if not self._skip_directory(item)]

            for file_name in files:
                path = current / file_name
                suffix = path.suffix.lower()
                if suffix not in allowed_suffixes:
                    continue
                if self._skip_file(path):
                    continue
                entry = self._build_entry(path, source)
                if entry is None:
                    continue
                discovered[entry.launch_target.lower()] = entry

    def _build_entry(self, path: Path, source: str) -> AppIndexEntry | None:
        stem = self._clean_display_name(path.stem)
        if not stem or self._is_noise_name(stem):
            return None

        aliases = self._generate_aliases(stem)
        return AppIndexEntry(
            name=stem,
            aliases=sorted(aliases),
            launch_target=str(path),
            launch_type="shortcut" if path.suffix.lower() in {".lnk", ".url"} else "executable",
            source=source,
            display_path=str(path),
        )

    def _score_entry(self, entry: AppIndexEntry, query: str) -> tuple[float, str]:
        haystacks = [self._normalize(entry.name), *[self._normalize(alias) for alias in entry.aliases]]
        best_score = 0.0
        reason = ""
        for candidate in haystacks:
            if not candidate:
                continue
            if candidate == query:
                return 1.0, "exact"
            if candidate.startswith(query):
                best_score = max(best_score, 0.93)
                reason = "prefix"
            elif query in candidate or candidate in query:
                best_score = max(best_score, 0.82)
                reason = "contains"

            ratio = SequenceMatcher(None, candidate, query).ratio()
            if ratio > best_score and ratio >= 0.62:
                best_score = ratio
                reason = "fuzzy"

        return best_score, reason

    @staticmethod
    def _source_priority(source: str) -> int:
        priorities = {
            "start_menu_user": 6,
            "start_menu_common": 5,
            "desktop_user": 4,
            "desktop_public": 3,
            "local_programs": 3,
            "program_files": 2,
            "program_files_x86": 2,
            "windows_apps": 1,
        }
        return priorities.get(source, 0)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()

    def _generate_aliases(self, name: str) -> set[str]:
        normalized = self._normalize(name)
        parts = normalized.split()
        aliases = {normalized, normalized.replace(" ", "")}
        if len(parts) > 1:
            aliases.add(" ".join(parts[:-1]))
            aliases.add("".join(part[0] for part in parts if part))
        return {alias.strip() for alias in aliases if alias.strip()}

    def _shortcut_directories(self) -> list[tuple[str, Path]]:
        appdata = Path(os.environ.get("APPDATA", ""))
        program_data = Path(os.environ.get("ProgramData", ""))
        user_profile = Path.home()
        return [
            ("start_menu_user", appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"),
            ("start_menu_common", program_data / "Microsoft" / "Windows" / "Start Menu" / "Programs"),
            ("desktop_user", user_profile / "Desktop"),
            ("desktop_public", Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"),
        ]

    def _executable_directories(self) -> list[tuple[str, Path]]:
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        return [
            ("local_programs", local_app_data / "Programs"),
            ("local_programs", local_app_data),
            ("program_files", program_files),
            ("program_files_x86", program_files_x86),
            ("windows_apps", local_app_data / "Microsoft" / "WindowsApps"),
        ]

    @staticmethod
    def _clean_display_name(name: str) -> str:
        cleaned = name.replace("_", " ").replace("-", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+(shortcut|launcher)$", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    @staticmethod
    def _skip_directory(name: str) -> bool:
        lowered = name.lower()
        return lowered in {
            "$recycle.bin",
            "cache",
            "crashpad",
            "installer",
            "installers",
            "logs",
            "temp",
            "templates",
            "uninstall information",
        }

    def _skip_file(self, path: Path) -> bool:
        stem = path.stem.lower()
        if path.name.lower() in {"desktop.ini"}:
            return True
        noise = ("uninstall", "updater", "update", "setup", "crashpad", "helper", "repair")
        return any(token in stem for token in noise)

    @staticmethod
    def _is_noise_name(name: str) -> bool:
        return name.lower() in {"readme", "license", "documentation", "install", "uninstall"}

    @staticmethod
    def _timestamp() -> str:
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _emit(emit: EventSink | None, message: str) -> None:
        if emit:
            emit(message)
