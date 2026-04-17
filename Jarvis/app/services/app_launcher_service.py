from __future__ import annotations

import os
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable

from app.core.models import AppConfig, AppIndexEntry, AppLaunchResult
from app.services.app_discovery_service import AppDiscoveryService


EventSink = Callable[[str], None]


class AppLauncherService:
    def __init__(self, config: AppConfig, discovery_service: AppDiscoveryService, logger) -> None:
        self.config = config
        self.discovery_service = discovery_service
        self.logger = logger

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def launch_app(self, requested_name: str, emit: EventSink | None = None) -> AppLaunchResult:
        result = self.resolve_app(requested_name, emit=emit)
        if not result.ok:
            return result

        try:
            self._launch_target(result.launch_target, result.launch_method)
            self._emit(emit, f"Launched {result.resolved_name or requested_name} using {result.launch_method}")
            return result
        except Exception as exc:
            if result.launch_method == "config_command":
                self._emit(emit, "Config command failed, falling back to the installed app index")
                fallback = self._resolve_from_index(requested_name, emit=emit)
                if fallback is not None:
                    try:
                        self._launch_target(fallback.launch_target, fallback.launch_method)
                        self._emit(emit, f"Launched {fallback.resolved_name or requested_name} using {fallback.launch_method}")
                        return fallback
                    except Exception:
                        self.logger.exception("Fallback launch from app index also failed for '%s'", requested_name)

            self.logger.exception("Failed to launch app '%s'", requested_name)
            return AppLaunchResult(
                ok=False,
                message=f"I found {result.resolved_name or requested_name}, but launching it failed: {exc}",
                requested_name=requested_name,
                resolved_name=result.resolved_name,
                confidence=result.confidence,
                launch_method=result.launch_method,
                launch_target=result.launch_target,
                source=result.source,
                suggestions=result.suggestions,
                details=result.details,
            )

    def resolve_app(self, requested_name: str, emit: EventSink | None = None) -> AppLaunchResult:
        normalized = self._normalize(requested_name)
        self._emit(emit, f"Resolving app target '{requested_name}'")

        alias_result = self._resolve_config_alias(normalized, requested_name)
        if alias_result and alias_result.ok:
            return alias_result

        direct_path = self._resolve_direct_path(requested_name)
        if direct_path:
            return direct_path

        browser_target = self._resolve_generic_browser(normalized, requested_name, emit=emit)
        if browser_target:
            return browser_target

        matches = self.discovery_service.search(normalized, limit=5)
        from_index = self._resolve_from_matches(requested_name, matches, emit=emit)
        if from_index:
            return from_index

        shell_result = self._resolve_shell_command(normalized, requested_name)
        if shell_result:
            return shell_result

        suggestions = self.discovery_service.suggestions(normalized, limit=5)
        if not suggestions:
            suggestions = self._alias_suggestions(normalized)

        return AppLaunchResult(
            ok=False,
            message=f"I could not find an installed app that looks like '{requested_name}'.",
            requested_name=requested_name,
            confidence=matches[0].score if matches else 0.0,
            suggestions=suggestions,
            details="Try a more specific name or refresh the app index from Settings.",
        )

    def _resolve_from_index(self, requested_name: str, emit: EventSink | None = None) -> AppLaunchResult | None:
        matches = self.discovery_service.search(requested_name, limit=5)
        return self._resolve_from_matches(requested_name, matches, emit=emit)

    def _resolve_from_matches(
        self,
        requested_name: str,
        matches,
        emit: EventSink | None = None,
    ) -> AppLaunchResult | None:
        if not matches:
            return None
        best = matches[0]
        if best.score < 0.66:
            return None
        self._emit(emit, f"App index matched '{best.entry.name}' with score {best.score:.2f}")
        return self._build_index_result(requested_name, best.entry, best.score, best.match_reason)

    def _resolve_generic_browser(
        self,
        normalized: str,
        requested_name: str,
        emit: EventSink | None = None,
    ) -> AppLaunchResult | None:
        if normalized not in {"browser", "my browser", "web browser", "default browser", "mein browser"}:
            return None

        preferred = (
            "Google Chrome",
            "Chrome",
            "Microsoft Edge",
            "Firefox",
            "Brave",
            "Opera",
        )
        best_match = None
        for candidate in preferred:
            matches = self.discovery_service.search(candidate, limit=1)
            if not matches:
                continue
            current = matches[0]
            if best_match is None or current.score > best_match.score:
                best_match = current

        if best_match and best_match.score >= 0.62:
            self._emit(emit, f"Resolved generic browser request to '{best_match.entry.name}'")
            return self._build_index_result(requested_name, best_match.entry, max(best_match.score, 0.88), "browser_preference")

        return self._resolve_shell_command("browser", requested_name)

    def _resolve_config_alias(self, normalized: str, requested_name: str) -> AppLaunchResult | None:
        if normalized not in self.config.app_aliases:
            return None

        target = self.config.app_aliases[normalized]
        if target.startswith(("http://", "https://")):
            return AppLaunchResult(
                ok=True,
                message=f"Opening {requested_name}.",
                requested_name=requested_name,
                resolved_name=requested_name,
                confidence=0.98,
                launch_method="config_url",
                launch_target=target,
                source="config_alias",
            )

        path = Path(os.path.expandvars(target)).expanduser()
        if path.exists():
            return AppLaunchResult(
                ok=True,
                message=f"Opening {requested_name}.",
                requested_name=requested_name,
                resolved_name=path.stem,
                confidence=0.99,
                launch_method="config_path",
                launch_target=str(path),
                source="config_alias",
            )

        resolved = shutil.which(target)
        if resolved:
            return AppLaunchResult(
                ok=True,
                message=f"Opening {requested_name}.",
                requested_name=requested_name,
                resolved_name=requested_name,
                confidence=0.95,
                launch_method="config_command",
                launch_target=target,
                source="config_alias",
            )

        return AppLaunchResult(
            ok=False,
            message=f"The configured alias for '{requested_name}' is not directly launchable.",
            requested_name=requested_name,
            resolved_name=requested_name,
            confidence=0.0,
            launch_method="",
            launch_target="",
            source="config_alias",
        )

    def _resolve_direct_path(self, requested_name: str) -> AppLaunchResult | None:
        expanded = Path(os.path.expandvars(requested_name)).expanduser()
        if not expanded.exists():
            return None
        return AppLaunchResult(
            ok=True,
            message=f"Opening {expanded.name}.",
            requested_name=requested_name,
            resolved_name=expanded.stem,
            confidence=1.0,
            launch_method="direct_path",
            launch_target=str(expanded),
            source="direct_path",
        )

    def _resolve_shell_command(self, normalized: str, requested_name: str) -> AppLaunchResult | None:
        common_shell = {
            "browser": "https://www.google.com",
            "calc": "calc",
            "calculator": "calc",
            "command prompt": "cmd",
            "explorer": "explorer",
            "file explorer": "explorer",
            "my browser": "https://www.google.com",
            "notepad": "notepad",
            "paint": "mspaint",
            "powershell": "powershell",
            "task manager": "taskmgr",
            "terminal": "wt",
            "web browser": "https://www.google.com",
        }
        if normalized not in common_shell:
            return None

        target = common_shell[normalized]
        method = "default_browser" if target.startswith("http") else "shell_command"
        return AppLaunchResult(
            ok=True,
            message=f"Opening {requested_name}.",
            requested_name=requested_name,
            resolved_name=requested_name,
            confidence=0.84,
            launch_method=method,
            launch_target=target,
            source="shell",
        )

    def _build_index_result(
        self,
        requested_name: str,
        entry: AppIndexEntry,
        confidence: float,
        reason: str,
    ) -> AppLaunchResult:
        method = f"{entry.source}:{entry.launch_type}"
        target_path = entry.target_path or self._resolve_shortcut_target(entry.launch_target)
        details = f"Matched via {reason} from {entry.source}"
        if target_path:
            details = f"{details}\nResolved target: {target_path}"
        return AppLaunchResult(
            ok=True,
            message=f"Opening {entry.name}.",
            requested_name=requested_name,
            resolved_name=entry.name,
            confidence=confidence,
            launch_method=method,
            launch_target=entry.launch_target,
            source=entry.source,
            details=details,
        )

    def _launch_target(self, target: str, method: str) -> None:
        if target.startswith(("http://", "https://")):
            webbrowser.open(target)
            return

        path = Path(os.path.expandvars(target)).expanduser()
        if path.exists():
            os.startfile(str(path))
            return
        if self._looks_like_path(target):
            raise FileNotFoundError(f"The launch target does not exist: {target}")

        if method == "default_browser":
            webbrowser.open(target)
            return

        try:
            subprocess.Popen([target], shell=False)
        except FileNotFoundError:
            subprocess.Popen(target, shell=True)

    def _resolve_shortcut_target(self, shortcut_path: str) -> str:
        path = Path(shortcut_path)
        if path.suffix.lower() != ".lnk" or not path.exists():
            return ""

        escaped_path = str(path).replace("'", "''")
        script = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$shortcut = $shell.CreateShortcut('{escaped_path}'); "
            "Write-Output $shortcut.TargetPath"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                check=True,
                capture_output=True,
                text=True,
                timeout=8,
            )
            return completed.stdout.strip()
        except Exception:
            return ""

    def _alias_suggestions(self, normalized: str) -> list[str]:
        scored: list[tuple[float, str]] = []
        for alias in self.config.app_aliases:
            ratio = self._ratio(normalized, alias)
            if ratio >= 0.55:
                scored.append((ratio, alias))
        scored.sort(reverse=True)
        return [alias for _, alias in scored[:5]]

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()

    @staticmethod
    def _ratio(left: str, right: str) -> float:
        from difflib import SequenceMatcher

        return SequenceMatcher(None, left, right).ratio()

    @staticmethod
    def _emit(emit: EventSink | None, message: str) -> None:
        if emit:
            emit(message)

    @staticmethod
    def _looks_like_path(value: str) -> bool:
        return any(marker in value for marker in ("\\", "/", ":"))
