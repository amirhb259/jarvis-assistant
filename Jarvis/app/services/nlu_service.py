from __future__ import annotations

import re
from dataclasses import dataclass

from app.commands.parser import NaturalLanguageParser
from app.core.models import AppConfig, CommandRequest
from app.services.app_discovery_service import AppDiscoveryService


@dataclass
class IntentCandidate:
    intent: str
    score: float
    slots: dict[str, object]
    reason: str


class NLUService:
    def __init__(self, config: AppConfig, app_discovery: AppDiscoveryService) -> None:
        self.config = config
        self.app_discovery = app_discovery
        self.legacy_parser = NaturalLanguageParser(config)
        self._noise_phrases = (
            "jarvis",
            "hey",
            "hey jarvis",
            "can you",
            "can u",
            "could you",
            "would you",
            "would you mind",
            "for me",
            "please",
            "pls",
            "i want to",
            "i want you to",
            "i need you to",
            "help me",
            "let me",
            "just",
            "kannst du",
            "koenntest du",
            "könntest du",
            "wuerdest du",
            "würdest du",
            "bitte",
            "ich moechte",
            "ich möchte",
            "ich will",
            "ich haette gern",
            "ich hätte gern",
            "mach mal",
            "mach bitte",
            "mal",
        )
        self._verb_synonyms = {
            "bring up": "open",
            "bring me to": "open",
            "fire up": "open",
            "go into": "open",
            "go to": "open",
            "launch": "open",
            "run": "open",
            "start up": "open",
            "start": "open",
            "starten": "open",
            "show me": "open",
            "oeffne": "open",
            "öffne": "open",
            "starte": "open",
            "mach auf": "open",
            "mache auf": "open",
            "aufmachen": "open",
            "ruf auf": "open",
            "rufe auf": "open",
            "suche": "search",
            "such": "search",
            "finde": "search",
            "schau nach": "search",
            "erstelle": "create",
            "lege an": "create",
            "mach": "create",
            "schreib": "type",
            "schreibe": "type",
            "tippe": "type",
            "fahre herunter": "shutdown",
            "starte neu": "restart",
            "sperre": "lock",
        }

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        self.legacy_parser.update_config(config)

    def interpret(self, raw_text: str, context: dict[str, object] | None = None) -> CommandRequest:
        context_data = context or {}
        clean = self._strip_wake_word(raw_text)
        clean = self._normalize_verbs(clean)
        clean = self._apply_contextual_rewrite(clean, context_data)
        normalized = self._normalize(clean)
        if not normalized:
            return CommandRequest(raw_text=raw_text, clean_text=clean, normalized_text=normalized, intent="empty")

        candidates = self._score_candidates(raw_text, clean, normalized, context_data)
        legacy = self.legacy_parser.parse(raw_text)
        if legacy.intent not in {"empty", "unknown"}:
            candidates.append(
                IntentCandidate(
                    intent=legacy.intent,
                    score=max(0.58, legacy.confidence or 0.58),
                    slots=legacy.slots,
                    reason="legacy_pattern_fallback",
                )
            )

        if not candidates:
            return CommandRequest(
                raw_text=raw_text,
                clean_text=clean,
                normalized_text=normalized,
                intent="unknown",
                confidence=0.0,
                diagnostics={"normalized_command": normalized},
            )

        candidates.sort(key=lambda item: item.score, reverse=True)
        top = candidates[0]
        alternatives = [
            {"intent": item.intent, "score": round(item.score, 3), "slots": item.slots, "reason": item.reason}
            for item in candidates[1:4]
        ]
        low_confidence = top.score < self.config.clarification_threshold
        ambiguous = bool(alternatives) and (top.score - alternatives[0]["score"] < 0.12)

        clarification_question = ""
        if top.score < self.config.low_confidence_threshold:
            clarification_question = self._clarification_question(top, alternatives)
            return CommandRequest(
                raw_text=raw_text,
                clean_text=clean,
                normalized_text=normalized,
                intent=top.intent,
                confidence=top.score,
                slots=top.slots,
                alternatives=alternatives,
                clarification_needed=True,
                clarification_question=clarification_question,
                diagnostics=self._diagnostics(clean, normalized, candidates),
                context_data=context_data,
            )

        if low_confidence and ambiguous:
            clarification_question = self._clarification_question(top, alternatives)

        return CommandRequest(
            raw_text=raw_text,
            clean_text=clean,
            normalized_text=normalized,
            intent=top.intent,
            confidence=top.score,
            slots=top.slots,
            alternatives=alternatives,
            clarification_needed=bool(clarification_question),
            clarification_question=clarification_question,
            diagnostics=self._diagnostics(clean, normalized, candidates),
            context_data=context_data,
        )

    def _score_candidates(
        self,
        raw_text: str,
        clean: str,
        normalized: str,
        context: dict[str, object],
    ) -> list[IntentCandidate]:
        del raw_text
        candidates: list[IntentCandidate] = []
        tokens = normalized.split()

        if any(word in normalized for word in ("screenshot", "bildschirmfoto", "schirmfoto", "snapshot")) or (
            "screen" in tokens and any(token in tokens for token in ("capture", "shot"))
        ):
            candidates.append(IntentCandidate("take_screenshot", 0.91, {}, "screenshot_keywords"))

        if any(
            phrase in normalized
            for phrase in (
                "what time",
                "tell me the time",
                "time is it",
                "current time",
                "wie spaet",
                "wie spat",
                "uhrzeit",
                "uhr",
            )
        ) or normalized == "time":
            candidates.append(IntentCandidate("tell_time", 0.92, {}, "time_keywords"))

        if any(
            phrase in normalized
            for phrase in (
                "what date",
                "tell me the date",
                "today date",
                "current date",
                "welches datum",
                "heutiges datum",
                "welcher tag",
            )
        ) or normalized == "date":
            candidates.append(IntentCandidate("tell_date", 0.9, {}, "date_keywords"))

        candidates.extend(self._score_search(clean, normalized, context))
        candidates.extend(self._score_open(clean, normalized, context))
        candidates.extend(self._score_create(clean))
        candidates.extend(self._score_volume(normalized))
        candidates.extend(self._score_system(normalized))
        candidates.extend(self._score_type_text(clean, normalized))
        candidates.extend(self._score_mouse(clean, normalized))
        candidates.extend(self._score_focus_window(clean, normalized, context))
        candidates.extend(self._score_clipboard(clean, normalized, context))
        return candidates

    def _score_search(self, clean: str, normalized: str, context: dict[str, object]) -> list[IntentCandidate]:
        candidates: list[IntentCandidate] = []
        has_search_terms = any(
            word in normalized
            for word in ("search", "find", "look up", "lookup", "play", "such", "suche", "finde")
        )
        last_target = str(context.get("last_target", "")).lower()
        last_website = str(context.get("last_website", "")).lower()
        follow_up = self._is_follow_up(normalized)

        if "youtube" in normalized and has_search_terms:
            query = self._extract_search_query(clean, "youtube")
            if query:
                candidates.append(IntentCandidate("search_youtube", 0.9, {"query": query}, "youtube_search"))

        google_as_search = normalized.startswith("google ") and not any(
            word in normalized for word in (" open", "browser", "chrome")
        )
        if has_search_terms or google_as_search:
            query = self._extract_search_query(clean, "google")
            if query:
                score = 0.75 if "youtube" not in normalized else 0.5
                if follow_up and "youtube" in f"{last_target} {last_website}":
                    score = 0.58
                candidates.append(IntentCandidate("search_google", score, {"query": query}, "search_keywords"))

        if any(word in normalized for word in ("search", "such", "suche", "finde", "find")) and any(
            word in normalized for word in ("dort", "da", "there", "it")
        ):
            query = self._extract_contextual_query(clean)
            if query and "youtube" in f"{last_target} {last_website}":
                candidates.append(IntentCandidate("search_youtube", 0.87, {"query": query}, "contextual_youtube_search"))
            elif query:
                candidates.append(IntentCandidate("search_google", 0.7, {"query": query}, "contextual_search"))

        if has_search_terms and follow_up:
            follow_up_query = self._extract_contextual_query(clean)
            if follow_up_query and "youtube" in f"{last_target} {last_website}":
                candidates.append(IntentCandidate("search_youtube", 0.89, {"query": follow_up_query}, "workflow_followup_youtube"))
            elif follow_up_query and last_website:
                candidates.append(IntentCandidate("search_google", 0.74, {"query": follow_up_query}, "workflow_followup_web"))
        return candidates

    def _score_open(
        self,
        clean: str,
        normalized: str,
        context: dict[str, object],
    ) -> list[IntentCandidate]:
        candidates: list[IntentCandidate] = []
        if not any(
            word in normalized
            for word in ("open", "start", "launch", "run", "bring up", "go into", "go to", "browser", "mach", "ruf")
        ):
            return candidates

        target = self._extract_open_target(clean)
        if not target:
            last_target = str(context.get("last_target", "")).strip()
            if any(token in normalized for token in ("browser", "website", "site")) and last_target:
                target = last_target
            else:
                return candidates

        lowered_target = self._normalize(target)
        if lowered_target in self.config.known_websites or "." in lowered_target:
            candidates.append(IntentCandidate("open_website", 0.96, {"target": target}, "website_target"))

        app_score = 0.68
        app_matches = self.app_discovery.search(target, limit=3)
        if app_matches:
            app_score = min(0.97, 0.62 + (app_matches[0].score * 0.35))
        elif lowered_target in self.config.app_aliases:
            app_score = 0.92
        if lowered_target in self.config.known_websites or "." in lowered_target:
            app_score = min(app_score, 0.7)

        candidates.append(
            IntentCandidate(
                "open_app",
                app_score,
                {"target": target, "resolved_candidates": [match.entry.name for match in app_matches]},
                "open_action",
            )
        )
        return candidates

    def _score_create(self, clean: str) -> list[IntentCandidate]:
        candidates: list[IntentCandidate] = []
        folder_patterns = [
            r"(?:create|make|erstelle|lege an)\s+(?:a\s+|einen\s+|einen neuen\s+)?(?:folder|ordner)(?:\s+(?:at|in|on|auf dem|im)\s+(?P<location>.+?))?\s+(?:called|named|namens)\s+(?P<name>.+)",
            r"(?:create|make|erstelle|lege an)\s+(?P<name>.+?)\s+(?:folder|ordner)(?:\s+(?:at|in|on|auf dem|im)\s+(?P<location>.+))?",
            r"(?:erstelle|lege an|mach)\s+(?:auf dem|im|in)?\s*(?P<location>desktop|documents|downloads|musik|music|bilder|pictures|videos|dokumente)?\s*(?:einen\s+)?ordner(?:\s+(?:namens|mit dem namen))\s+(?P<name>.+)",
            r"(?:create|erstelle|lege an)\s+(?:auf dem|im|in)\s+(?P<location>desktop|documents|downloads|musik|music|bilder|pictures|videos|dokumente)\s+(?:einen\s+)?(?:folder|ordner)\s+(?:namens|called|named)\s+(?P<name>.+)",
            r"(?:make|create)\s+(?:me\s+)?(?:a\s+)?folder\s+(?:named|called)\s+(?P<name>.+?)(?:\s+(?:on|in|at)\s+(?P<location>.+))?",
        ]
        file_patterns = [
            r"(?:create|make|erstelle|lege an)\s+(?:a\s+|eine\s+)?(?:file|datei)(?:\s+(?:at|in|on|auf dem|im)\s+(?P<location>.+?))?\s+(?:called|named|namens)\s+(?P<name>.+)",
            r"(?:create|make|erstelle|lege an)\s+(?P<name>.+?)\s+(?:file|datei)(?:\s+(?:at|in|on|auf dem|im)\s+(?P<location>.+))?",
            r"(?:erstelle|lege an|mach)\s+(?:auf dem|im|in)?\s*(?P<location>desktop|documents|downloads|dokumente)?\s*(?:eine\s+)?datei(?:\s+(?:namens|mit dem namen))\s+(?P<name>.+)",
            r"(?:create|erstelle|lege an)\s+(?:auf dem|im|in)\s+(?P<location>desktop|documents|downloads|dokumente)\s+(?:eine\s+)?(?:file|datei)\s+(?:namens|called|named)\s+(?P<name>.+)",
            r"(?:make|create)\s+(?:me\s+)?(?:a\s+)?file\s+(?:named|called)\s+(?P<name>.+?)(?:\s+(?:on|in|at)\s+(?P<location>.+))?",
        ]

        for pattern in folder_patterns:
            match = re.fullmatch(pattern, clean, flags=re.IGNORECASE)
            if match:
                candidates.append(
                    IntentCandidate(
                        "create_folder",
                        0.88,
                        {
                            "location": (match.groupdict().get("location") or "current folder").strip(),
                            "name": match.groupdict()["name"].strip().strip('"'),
                        },
                        "folder_pattern",
                    )
                )
                break

        for pattern in file_patterns:
            match = re.fullmatch(pattern, clean, flags=re.IGNORECASE)
            if match:
                candidates.append(
                    IntentCandidate(
                        "create_file",
                        0.88,
                        {
                            "location": (match.groupdict().get("location") or "current folder").strip(),
                            "name": match.groupdict()["name"].strip().strip('"'),
                        },
                        "file_pattern",
                    )
                )
                break
        return candidates

    def _score_volume(self, normalized: str) -> list[IntentCandidate]:
        candidates: list[IntentCandidate] = []
        if "mute" in normalized and "unmute" not in normalized:
            candidates.append(IntentCandidate("mute_volume", 0.9, {}, "mute_keyword"))
        if "unmute" in normalized:
            candidates.append(IntentCandidate("unmute_volume", 0.9, {}, "unmute_keyword"))
        if "stumm" in normalized:
            candidates.append(IntentCandidate("mute_volume", 0.88, {}, "mute_keyword_de"))

        set_match = re.search(r"volume\s+(?:to|at)\s+(?P<value>\d{1,3})", normalized)
        if set_match:
            candidates.append(IntentCandidate("set_volume", 0.92, {"value": int(set_match.group("value"))}, "set_volume"))
        set_match_de = re.search(r"lautstaerke\s+(?:auf|bei)\s+(?P<value>\d{1,3})", normalized)
        if set_match_de:
            candidates.append(IntentCandidate("set_volume", 0.92, {"value": int(set_match_de.group("value"))}, "set_volume_de"))

        if any(word in normalized for word in ("volume up", "turn up", "increase volume", "louder", "lauter", "lautstaerke hoch")):
            candidates.append(IntentCandidate("volume_up", 0.86, {"value": self._extract_number(normalized, 10)}, "volume_up"))
        if any(word in normalized for word in ("volume down", "turn down", "decrease volume", "quieter", "lower volume", "leiser", "lautstaerke runter")):
            candidates.append(IntentCandidate("volume_down", 0.86, {"value": self._extract_number(normalized, 10)}, "volume_down"))
        return candidates

    def _score_system(self, normalized: str) -> list[IntentCandidate]:
        candidates: list[IntentCandidate] = []
        if any(phrase in normalized for phrase in ("cancel shutdown", "abort shutdown", "cancel restart", "abort restart", "abbrechen", "stoppe herunterfahren")):
            candidates.append(IntentCandidate("cancel_system_action", 0.95, {}, "cancel_system_action"))
        if any(phrase in normalized for phrase in ("shutdown", "turn off the pc", "power off the pc", "herunterfahren", "ausschalten")) or re.search(r"fahr(?:e)? .* herunter", normalized):
            candidates.append(IntentCandidate("shutdown_pc", 0.94, {}, "shutdown_keyword"))
        if any(phrase in normalized for phrase in ("restart", "reboot", "neu starten", "neustarten")):
            candidates.append(IntentCandidate("restart_pc", 0.94, {}, "restart_keyword"))
        if any(phrase in normalized for phrase in ("lock screen", "lock the pc", "lock computer", "bildschirm sperren", "sperre den pc", "lock windows")):
            candidates.append(IntentCandidate("lock_pc", 0.9, {}, "lock_keyword"))
        return candidates

    def _score_type_text(self, clean: str, normalized: str) -> list[IntentCandidate]:
        match = re.fullmatch(r"(?:type|write|schreib|schreibe|tippe)\s+(?:this\s+|that\s+|das\s+)?(?P<text>.+)", clean, flags=re.IGNORECASE)
        if match and "mouse" not in normalized:
            return [IntentCandidate("type_text", 0.84, {"text": match.group("text").strip().strip('"')}, "type_text")]
        return []

    def _score_focus_window(
        self,
        clean: str,
        normalized: str,
        context: dict[str, object],
    ) -> list[IntentCandidate]:
        match = re.search(
            r"(?:focus|activate|bring to front|switch to|fokussiere|aktiviere|hol nach vorn|in den vordergrund)\s+(?P<target>.+)",
            clean,
            flags=re.IGNORECASE,
        )
        if match:
            target = match.group("target").strip(" .")
            target = re.sub(r"^(?:das|den|die|the)\s+", "", target, flags=re.IGNORECASE)
            if target.lower() in {"es", "it", "that", "das"}:
                target = str(context.get("last_window_title") or context.get("last_app") or context.get("last_target", "")).strip()
            if target:
                return [IntentCandidate("focus_window", 0.86, {"target": target}, "focus_window")]

        if self._is_follow_up(normalized) and any(token in normalized for token in ("fokuss", "focus", "activate")):
            last_window = str(context.get("last_window_title") or context.get("last_app") or context.get("last_target", "")).strip()
            if last_window:
                return [IntentCandidate("focus_window", 0.78, {"target": last_window}, "focus_window_context")]
        return []

    def _score_clipboard(
        self,
        clean: str,
        normalized: str,
        context: dict[str, object],
    ) -> list[IntentCandidate]:
        candidates: list[IntentCandidate] = []
        if any(
            phrase in normalized
            for phrase in (
                "read clipboard",
                "what is in my clipboard",
                "what s in my clipboard",
                "show clipboard",
                "zwischenablage lesen",
                "was ist im clipboard",
                "was ist in der zwischenablage",
            )
        ):
            candidates.append(IntentCandidate("clipboard_read", 0.92, {}, "clipboard_read"))

        if "clipboard" in normalized or "zwischenablage" in normalized:
            text = ""
            quoted = re.search(r'["“](?P<text>.+?)["”]', clean)
            if quoted:
                text = quoted.group("text").strip()
            if not text:
                patterns = (
                    r"(?:copy|kopiere|kopier|packe|pack|put)\s+(?P<text>.+?)\s+(?:to clipboard|ins clipboard|in die zwischenablage)",
                    r"(?:schreib|schreibe|write)\s+(?P<text>.+?)\s+(?:ins clipboard|in die zwischenablage|to clipboard)",
                )
                for pattern in patterns:
                    match = re.search(pattern, clean, flags=re.IGNORECASE)
                    if match:
                        text = match.group("text").strip(" .")
                        break
            if text.lower() in {"that", "this", "it", "das", "es"}:
                text = ""
            if not text and re.search(r"\b(das|es|that|it|this)\b", normalized):
                text = self._contextual_payload(context)
            if text:
                candidates.append(IntentCandidate("clipboard_write", 0.88, {"text": text}, "clipboard_write"))
        return candidates

    def _score_mouse(self, clean: str, normalized: str) -> list[IntentCandidate]:
        candidates: list[IntentCandidate] = []
        move_match = re.search(
            r"(?:move|bewege)\s+(?:the |die )?(?:mouse|maus)(?:\s+(?P<direction>up|down|left|right|hoch|runter|links|rechts))?(?:\s+(?:by |um )?(?P<distance>\d+))?",
            clean,
            flags=re.IGNORECASE,
        )
        if move_match:
            candidates.append(
                IntentCandidate(
                    "move_mouse",
                    0.87,
                    {
                        "direction": self._normalize_direction(move_match.group("direction") or "right"),
                        "distance": int(move_match.group("distance") or 120),
                    },
                    "mouse_move",
                )
            )

        click_match = re.search(r"(?:(left|right|links|rechts)\s+)?(?:click|klick)", clean, flags=re.IGNORECASE)
        if click_match and any(word in normalized for word in ("mouse", "maus", "click", "klick")):
            candidates.append(
                IntentCandidate(
                    "click_mouse",
                    0.84,
                    {"button": self._normalize_button(click_match.group(1) or "left")},
                    "mouse_click",
                )
            )
        return candidates

    def _extract_open_target(self, text: str) -> str:
        working = text
        for source, target in self._verb_synonyms.items():
            working = re.sub(rf"\b{re.escape(source)}\b", target, working, flags=re.IGNORECASE)
        match = re.search(r"\bopen\b\s+(?P<target>.+?)$", working, flags=re.IGNORECASE)
        if not match:
            match = re.search(r"\bmach\b\s+(?P<target>.+?)\s+auf$", text, flags=re.IGNORECASE)
        if not match:
            match = re.search(r"(?P<target>.+?)\s+\bopen\b$", working, flags=re.IGNORECASE)
        if not match and any(token in text.lower() for token in ("browser", "website", "site")):
            return "browser"
        if not match:
            return ""
        target = match.group("target").strip()
        target = re.sub(r"^(?:the|my|mein|meine)\s+", "", target, flags=re.IGNORECASE)
        target = re.sub(r"\b(app|application|program)\b", "", target, flags=re.IGNORECASE)
        target = re.sub(r"\b(for me|please|bitte)\b", "", target, flags=re.IGNORECASE)
        target = re.sub(r"\s+", " ", target).strip(" .")
        return target

    def _extract_search_query(self, text: str, engine: str) -> str:
        cleaned = text
        if engine == "youtube":
            cleaned = re.sub(r"\bon youtube\b", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\byoutube\b", "", cleaned, flags=re.IGNORECASE)
        if engine == "google":
            cleaned = re.sub(r"\bon google\b", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\bgoogle\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(search|look up|lookup|find|play|such|suche|finde)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bfor\b|\bnach\b|\babout\b", "", cleaned, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", cleaned).strip(" .")

    def _extract_contextual_query(self, text: str) -> str:
        query = re.sub(r"\b(search|such|suche|finde|find)\b", "", text, flags=re.IGNORECASE)
        query = re.sub(r"\b(dort|da|there|it)\b", "", query, flags=re.IGNORECASE)
        query = re.sub(r"\bnach\b|\bfor\b|\babout\b", "", query, flags=re.IGNORECASE)
        query = re.sub(r"\b(und|and|dann|danach|jetzt|nun|then|next)\b", "", query, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", query).strip(" .")

    def _clarification_question(self, top: IntentCandidate, alternatives: list[dict[str, object]]) -> str:
        if top.intent == "open_app" and top.slots.get("target"):
            return f"Do you want me to open '{top.slots['target']}'?"
        if alternatives:
            return f"Do you mean '{top.intent}' or '{alternatives[0]['intent']}'?"
        return "Can you rephrase that command a little more clearly?"

    def _diagnostics(self, clean: str, normalized: str, candidates: list[IntentCandidate]) -> dict[str, object]:
        return {
            "clean_command": clean,
            "normalized_command": normalized,
            "candidates": [
                {"intent": item.intent, "score": round(item.score, 3), "reason": item.reason, "slots": item.slots}
                for item in sorted(candidates, key=lambda entry: entry.score, reverse=True)[:5]
            ],
        }

    def _strip_wake_word(self, text: str) -> str:
        cleaned = text.strip()
        pattern = rf"^(?:{re.escape(self.config.wake_word)}[\s,:\-]+)"
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        for phrase in self._noise_phrases:
            cleaned = re.sub(rf"\b{re.escape(phrase)}\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip(" ,.")

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = (
            text.lower()
            .replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
        )
        normalized = re.sub(r"[^\w\s:\\/.%-]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _normalize_verbs(self, text: str) -> str:
        updated = text
        ordered = sorted(self._verb_synonyms.items(), key=lambda item: len(item[0]), reverse=True)
        for source, target in ordered:
            updated = re.sub(rf"\b{re.escape(source)}\b", target, updated, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", updated).strip()

    def _apply_contextual_rewrite(self, text: str, context: dict[str, object]) -> str:
        if not context:
            return text
        updated = text
        last_target = str(context.get("last_target", "")).strip()
        last_website = str(context.get("last_website", "")).strip()
        if (last_target or last_website) and re.search(r"\b(dort|da|there|it)\b", updated, flags=re.IGNORECASE):
            replacement = last_website or last_target
            updated = re.sub(r"\b(dort|da|there|it)\b", replacement, updated, flags=re.IGNORECASE)
        return updated

    @staticmethod
    def _is_follow_up(normalized: str) -> bool:
        return normalized.startswith(("und ", "and ", "dann ", "danach ", "jetzt ", "nun ", "then ", "next "))

    @staticmethod
    def _contextual_payload(context: dict[str, object]) -> str:
        for key in ("last_response", "last_created_path", "last_target"):
            value = str(context.get(key, "")).strip()
            if value:
                return value
        return ""

    @staticmethod
    def _normalize_button(button: str) -> str:
        value = button.lower()
        if value == "links":
            return "left"
        if value == "rechts":
            return "right"
        return value

    @staticmethod
    def _normalize_direction(direction: str) -> str:
        value = direction.lower()
        mapping = {
            "hoch": "up",
            "runter": "down",
            "links": "left",
            "rechts": "right",
        }
        return mapping.get(value, value)

    @staticmethod
    def _extract_number(text: str, default: int) -> int:
        match = re.search(r"(\d{1,3})", text)
        return int(match.group(1)) if match else default
