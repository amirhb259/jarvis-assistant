from __future__ import annotations

import re

from app.core.models import AppConfig, BrainEntity, CommandRequest


class EntityExtractorService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def extract(self, request: CommandRequest) -> list[BrainEntity]:
        entities: list[BrainEntity] = []
        slots = request.slots

        if "target" in slots:
            target = str(slots["target"]).strip()
            if target:
                entities.append(self._entity("target", target, "target", request.confidence))
                if target.lower() in self.config.known_websites or "." in target:
                    entities.append(self._entity("website", target, "resource", request.confidence))
                else:
                    entities.append(self._entity("app", target, "resource", request.confidence))

        if "query" in slots:
            entities.append(self._entity("query", str(slots["query"]), "content", request.confidence))

        if "name" in slots:
            kind = "folder_name" if request.intent == "create_folder" else "file_name"
            entities.append(self._entity(kind, str(slots["name"]), "name", request.confidence))

        if "location" in slots:
            location = str(slots["location"]).strip()
            entities.append(self._entity("path", location, "location", request.confidence))

        if "text" in slots:
            text = str(slots["text"])
            entities.append(
                BrainEntity(
                    kind="text",
                    value=text,
                    role="payload",
                    normalized_value=text,
                    confidence=request.confidence,
                    metadata={"length": len(text)},
                )
            )

        if request.intent in {"clipboard_read", "clipboard_write"}:
            entities.append(self._entity("clipboard", "clipboard", "resource", request.confidence))

        if "value" in slots:
            entities.append(
                BrainEntity(
                    kind="number",
                    value=str(slots["value"]),
                    role="parameter",
                    normalized_value=str(slots["value"]),
                    confidence=request.confidence,
                )
            )

        if "direction" in slots:
            entities.append(self._entity("direction", str(slots["direction"]), "parameter", request.confidence))

        if "button" in slots:
            entities.append(self._entity("button", str(slots["button"]), "parameter", request.confidence))

        if request.intent == "focus_window":
            entities.append(self._entity("window", str(slots.get("target", "")), "resource", request.confidence))

        if request.intent in {"shutdown_pc", "restart_pc", "lock_pc", "cancel_system_action"}:
            entities.append(self._entity("system_action", request.intent, "action", request.confidence))

        deduped: list[BrainEntity] = []
        seen: set[tuple[str, str, str]] = set()
        for entity in entities:
            key = (entity.kind, entity.role, entity.normalized_value)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entity)
        return deduped

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9:\\/.%-]+", " ", value.lower())).strip()

    def _entity(self, kind: str, value: str, role: str, confidence: float) -> BrainEntity:
        return BrainEntity(
            kind=kind,
            value=value,
            role=role,
            normalized_value=self._normalize(value),
            confidence=confidence,
        )
