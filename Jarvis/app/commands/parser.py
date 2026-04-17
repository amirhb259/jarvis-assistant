from __future__ import annotations

import re

from app.core.models import AppConfig, CommandRequest


class NaturalLanguageParser:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def parse(self, raw_text: str) -> CommandRequest:
        clean = self._strip_wake_prefix(raw_text)
        normalized = self._normalize(clean)
        if not normalized:
            return CommandRequest(raw_text=raw_text, clean_text=clean, normalized_text=normalized, intent="empty")

        for matcher in (
            self._match_cancel_system_action,
            self._match_screenshot,
            self._match_time,
            self._match_date,
            self._match_search_youtube,
            self._match_search_google,
            self._match_create_folder,
            self._match_create_file,
            self._match_volume,
            self._match_system_actions,
            self._match_type_text,
            self._match_mouse,
            self._match_click,
            self._match_open,
        ):
            request = matcher(raw_text, clean, normalized)
            if request:
                return request

        return CommandRequest(
            raw_text=raw_text,
            clean_text=clean,
            normalized_text=normalized,
            intent="unknown",
        )

    def _strip_wake_prefix(self, text: str) -> str:
        value = text.strip()
        pattern = rf"^(?:{re.escape(self.config.wake_word)}[\s,:\-]+)"
        return re.sub(pattern, "", value, flags=re.IGNORECASE).strip()

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def _build_request(
        self,
        raw_text: str,
        clean: str,
        normalized: str,
        intent: str,
        **slots: object,
    ) -> CommandRequest:
        return CommandRequest(
            raw_text=raw_text,
            clean_text=clean,
            normalized_text=normalized,
            intent=intent,
            slots=slots,
        )

    def _match_cancel_system_action(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        if normalized in {"cancel shutdown", "abort shutdown", "cancel restart", "abort restart"}:
            return self._build_request(raw_text, clean, normalized, "cancel_system_action")
        return None

    def _match_screenshot(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        if any(token in normalized for token in ("take a screenshot", "take screenshot", "screenshot", "screen shot")):
            return self._build_request(raw_text, clean, normalized, "take_screenshot")
        return None

    def _match_time(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        if normalized in {"time", "tell me the time", "what is the time", "what's the time"}:
            return self._build_request(raw_text, clean, normalized, "tell_time")
        return None

    def _match_date(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        if normalized in {"date", "tell me the date", "what is the date", "what's the date", "today's date"}:
            return self._build_request(raw_text, clean, normalized, "tell_date")
        return None

    def _match_search_youtube(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        patterns = [
            r"search youtube for (?P<query>.+)",
            r"look up (?P<query>.+) on youtube",
            r"find (?P<query>.+) on youtube",
        ]
        for pattern in patterns:
            match = re.fullmatch(pattern, clean, flags=re.IGNORECASE)
            if match:
                return self._build_request(
                    raw_text,
                    clean,
                    normalized,
                    "search_youtube",
                    query=match.group("query").strip(),
                )
        return None

    def _match_search_google(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        patterns = [
            r"search google for (?P<query>.+)",
            r"search for (?P<query>.+)",
            r"google (?P<query>.+)",
            r"look up (?P<query>.+)",
        ]
        for pattern in patterns:
            match = re.fullmatch(pattern, clean, flags=re.IGNORECASE)
            if match:
                return self._build_request(
                    raw_text,
                    clean,
                    normalized,
                    "search_google",
                    query=match.group("query").strip(),
                )
        return None

    def _match_create_folder(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        pattern = (
            r"(?:create|make)\s+(?:a\s+)?folder"
            r"(?:\s+(?:on|in)\s+(?P<location>[a-zA-Z ]+?))?"
            r"\s+(?:called|named)\s+(?P<name>[^.]+)"
        )
        match = re.fullmatch(pattern, clean, flags=re.IGNORECASE)
        if match:
            return self._build_request(
                raw_text,
                clean,
                normalized,
                "create_folder",
                location=(match.group("location") or "current folder").strip(),
                name=match.group("name").strip(),
            )
        return None

    def _match_create_file(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        pattern = (
            r"(?:create|make)\s+(?:a\s+)?file"
            r"(?:\s+(?:on|in)\s+(?P<location>[a-zA-Z ]+?))?"
            r"\s+(?:called|named)\s+(?P<name>.+)"
        )
        match = re.fullmatch(pattern, clean, flags=re.IGNORECASE)
        if match:
            return self._build_request(
                raw_text,
                clean,
                normalized,
                "create_file",
                location=(match.group("location") or "current folder").strip(),
                name=match.group("name").strip(),
            )
        return None

    def _match_volume(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        if normalized in {"mute", "mute volume"}:
            return self._build_request(raw_text, clean, normalized, "mute_volume")
        if normalized in {"unmute", "unmute volume"}:
            return self._build_request(raw_text, clean, normalized, "unmute_volume")

        set_match = re.fullmatch(r"set volume to (?P<value>\d{1,3})", clean, flags=re.IGNORECASE)
        if set_match:
            return self._build_request(
                raw_text,
                clean,
                normalized,
                "set_volume",
                value=int(set_match.group("value")),
            )

        up_match = re.fullmatch(
            r"(?:volume up|increase volume|turn volume up)(?: by (?P<value>\d{1,3}))?",
            clean,
            flags=re.IGNORECASE,
        )
        if up_match:
            return self._build_request(
                raw_text,
                clean,
                normalized,
                "volume_up",
                value=int(up_match.group("value") or 10),
            )

        down_match = re.fullmatch(
            r"(?:volume down|decrease volume|turn volume down)(?: by (?P<value>\d{1,3}))?",
            clean,
            flags=re.IGNORECASE,
        )
        if down_match:
            return self._build_request(
                raw_text,
                clean,
                normalized,
                "volume_down",
                value=int(down_match.group("value") or 10),
            )
        return None

    def _match_system_actions(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        if normalized in {"shutdown", "shutdown pc", "shutdown the pc", "shutdown the computer"}:
            return self._build_request(raw_text, clean, normalized, "shutdown_pc")
        if normalized in {"restart", "restart pc", "restart the pc", "restart the computer"}:
            return self._build_request(raw_text, clean, normalized, "restart_pc")
        if normalized in {"lock pc", "lock the pc", "lock the computer", "lock screen"}:
            return self._build_request(raw_text, clean, normalized, "lock_pc")
        return None

    def _match_type_text(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        match = re.fullmatch(r"(?:type text for me|type)\s+(.+)", clean, flags=re.IGNORECASE)
        if match:
            return self._build_request(
                raw_text,
                clean,
                normalized,
                "type_text",
                text=match.group(1).strip().strip('"'),
            )
        return None

    def _match_mouse(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        match = re.fullmatch(
            r"move (?:the )?mouse(?:\s+(?P<direction>up|down|left|right))?(?:\s+(?:by )?(?P<distance>\d+))?",
            clean,
            flags=re.IGNORECASE,
        )
        if match:
            return self._build_request(
                raw_text,
                clean,
                normalized,
                "move_mouse",
                direction=(match.group("direction") or "right").lower(),
                distance=int(match.group("distance") or 120),
            )
        return None

    def _match_click(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        match = re.fullmatch(r"(?:(left|right)\s+)?click(?: the mouse)?", clean, flags=re.IGNORECASE)
        if match:
            return self._build_request(
                raw_text,
                clean,
                normalized,
                "click_mouse",
                button=(match.group(1) or "left").lower(),
            )
        return None

    def _match_open(self, raw_text: str, clean: str, normalized: str) -> CommandRequest | None:
        match = re.fullmatch(r"open\s+(.+)", clean, flags=re.IGNORECASE)
        if not match:
            return None

        target = match.group(1).strip()
        lowered = target.lower()
        if lowered in self.config.known_websites or "." in lowered or lowered.startswith(("http://", "https://", "www.")):
            return self._build_request(raw_text, clean, normalized, "open_website", target=target)
        return self._build_request(raw_text, clean, normalized, "open_app", target=target)
