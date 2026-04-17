from __future__ import annotations

import json
from pathlib import Path

from app.core.models import AppConfig
from app.core.paths import CONFIG_DIR, ensure_runtime_dirs


class ConfigManager:
    def __init__(self, config_path: Path | None = None) -> None:
        ensure_runtime_dirs()
        self.config_path = config_path or CONFIG_DIR / "settings.json"
        self.example_path = CONFIG_DIR / "settings.example.json"
        self.config = self._load()

    def _load(self) -> AppConfig:
        if not self.example_path.exists():
            self._write(self.example_path, AppConfig())

        if not self.config_path.exists():
            default_config = AppConfig()
            self._write(self.config_path, default_config)
            return default_config

        with self.config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return AppConfig.from_dict(data)

    def _write(self, path: Path, config: AppConfig) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(config.to_dict(), handle, indent=2)

    def save(self) -> None:
        self._write(self.config_path, self.config)

    def update(self, **kwargs: object) -> AppConfig:
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.save()
        return self.config
