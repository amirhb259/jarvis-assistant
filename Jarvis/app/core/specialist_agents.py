from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SpecialistAgent:
    name: str
    description: str
    tools: tuple[str, ...]


class DesktopAgent(SpecialistAgent):
    def __init__(self) -> None:
        super().__init__(
            name="desktop_agent",
            description="Steuert Desktop-Aktionen wie Apps öffnen, Maus, Tastatur und Screenshots.",
            tools=(
                "open_app",
                "take_screenshot",
                "move_mouse",
                "click_mouse",
                "type_text",
                "focus_window",
                "clipboard_read",
                "clipboard_write",
            ),
        )


class BrowserAgent(SpecialistAgent):
    def __init__(self) -> None:
        super().__init__(
            name="browser_agent",
            description="Steuert Webseiten, Browser-Ziele und Websuche.",
            tools=("open_website", "search_google", "search_youtube"),
        )


class FileSystemAgent(SpecialistAgent):
    def __init__(self) -> None:
        super().__init__(
            name="filesystem_agent",
            description="Verarbeitet Datei- und Ordneroperationen.",
            tools=("create_folder", "create_file"),
        )


class SystemControlAgent(SpecialistAgent):
    def __init__(self) -> None:
        super().__init__(
            name="system_control_agent",
            description="Führt Systemsteuerungsaktionen mit Guardrails aus.",
            tools=(
                "tell_time",
                "tell_date",
                "volume_up",
                "volume_down",
                "set_volume",
                "mute_volume",
                "unmute_volume",
                "shutdown_pc",
                "restart_pc",
                "lock_pc",
                "cancel_system_action",
            ),
        )


class ResponseAgent(SpecialistAgent):
    def __init__(self) -> None:
        super().__init__(
            name="response_agent",
            description="Erzeugt natürliche Antworten aus strukturierten Ausführungsresultaten.",
            tools=("generate_response",),
        )
