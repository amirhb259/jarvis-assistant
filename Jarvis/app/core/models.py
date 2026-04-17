from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.paths import APP_INDEX_FILE, DATA_DIR, LOG_DIR, SCREENSHOT_DIR


def _default_blocked_paths() -> list[str]:
    return [
        r"C:\Windows",
        r"C:\Windows\System32",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"%USERPROFILE%\AppData",
    ]


def _default_app_aliases() -> dict[str, str]:
    return {
        "browser": "msedge",
        "calculator": "calc",
        "chrome": "chrome",
        "cmd": "cmd",
        "command prompt": "cmd",
        "dc": "discord",
        "discord": "discord",
        "edge": "msedge",
        "file explorer": "explorer",
        "explorer": "explorer",
        "google chrome": "chrome",
        "notepad": "notepad",
        "paint": "mspaint",
        "powershell": "powershell",
        "spotify": "spotify",
        "task manager": "taskmgr",
        "terminal": "wt",
        "visual studio code": "code",
        "vs code": "code",
        "vscode": "code",
    }


def _default_known_websites() -> dict[str, str]:
    return {
        "google": "https://www.google.com",
        "gmail": "https://mail.google.com",
        "github": "https://github.com",
        "reddit": "https://www.reddit.com",
        "stack overflow": "https://stackoverflow.com",
        "youtube": "https://www.youtube.com",
    }


@dataclass
class AppConfig:
    assistant_name: str = "Jarvis"
    voice_input_enabled: bool = True
    voice_output_enabled: bool = True
    dangerous_system_actions_enabled: bool = True
    wake_word_enabled: bool = False
    wake_word: str = "jarvis"
    vosk_model_path: str = ""
    voice_input_device: str = ""
    screenshot_directory: str = str(SCREENSHOT_DIR)
    history_file: str = str(DATA_DIR / "history.json")
    log_file: str = str(LOG_DIR / "jarvis.log")
    app_index_file: str = str(APP_INDEX_FILE)
    confirmation_timeout_seconds: int = 15
    typing_delay_seconds: int = 3
    system_action_delay_seconds: int = 20
    mouse_max_distance: int = 240
    clipboard_max_length: int = 800
    low_confidence_threshold: float = 0.48
    clarification_threshold: float = 0.62
    app_discovery_max_depth: int = 3
    app_index_refresh_on_startup: bool = True
    blocked_paths: list[str] = field(default_factory=_default_blocked_paths)
    app_aliases: dict[str, str] = field(default_factory=_default_app_aliases)
    known_websites: dict[str, str] = field(default_factory=_default_known_websites)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        defaults = cls()
        payload = asdict(defaults)
        payload.update(data or {})
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommandRequest:
    raw_text: str
    clean_text: str
    normalized_text: str
    intent: str
    confidence: float = 0.0
    slots: dict[str, Any] = field(default_factory=dict)
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)
    plan: BrainPlan | None = None
    context_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    ok: bool
    message: str
    intent: str = ""
    confidence: float = 0.0
    details: str = ""
    requires_confirmation: bool = False
    confirmation_title: str = ""
    confirmation_message: str = ""
    pending_request: CommandRequest | None = None
    spoken_text: str = ""
    understood_target: str = ""
    selected_tool: str = ""
    selected_tools: list[str] = field(default_factory=list)
    plan_summary: str = ""
    launch_method: str = ""
    suggestions: list[str] = field(default_factory=list)
    extracted_entities: list[dict[str, Any]] = field(default_factory=list)
    planned_steps: list[dict[str, Any]] = field(default_factory=list)
    safety_flags: list[str] = field(default_factory=list)
    response_message: str = ""
    agent_trace: dict[str, Any] = field(default_factory=dict)
    execution_status: str = "pending"
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class WindowMatch:
    title: str
    handle: int
    process_name: str = ""
    score: float = 0.0


@dataclass
class HistoryEntry:
    timestamp: str
    role: str
    text: str
    intent: str = ""
    success: bool = True


@dataclass
class AppIndexEntry:
    name: str
    aliases: list[str]
    launch_target: str
    launch_type: str
    source: str
    display_path: str = ""
    target_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "aliases": self.aliases,
            "launch_target": self.launch_target,
            "launch_type": self.launch_type,
            "source": self.source,
            "display_path": self.display_path,
            "target_path": self.target_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppIndexEntry":
        return cls(
            name=str(data.get("name", "")),
            aliases=list(data.get("aliases", [])),
            launch_target=str(data.get("launch_target", "")),
            launch_type=str(data.get("launch_type", "")),
            source=str(data.get("source", "")),
            display_path=str(data.get("display_path", "")),
            target_path=str(data.get("target_path", "")),
        )


@dataclass
class AppMatch:
    entry: AppIndexEntry
    score: float
    match_reason: str


@dataclass
class AppLaunchResult:
    ok: bool
    message: str
    requested_name: str
    resolved_name: str = ""
    confidence: float = 0.0
    launch_method: str = ""
    launch_target: str = ""
    source: str = ""
    suggestions: list[str] = field(default_factory=list)
    details: str = ""


@dataclass
class BrainEntity:
    kind: str
    value: str
    role: str = ""
    normalized_value: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "role": self.role,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class BrainStep:
    description: str
    tool_name: str
    intent: str
    status: str = "planned"
    slots: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "tool_name": self.tool_name,
            "intent": self.intent,
            "status": self.status,
            "slots": self.slots,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class BrainPlan:
    intent: str
    selected_tool: str = ""
    confidence: float = 0.0
    summary: str = ""
    reasoning: str = ""
    entities: list[BrainEntity] = field(default_factory=list)
    steps: list[BrainStep] = field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: str = ""
    requires_confirmation: bool = False
    confirmation_reason: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "selected_tool": self.selected_tool,
            "confidence": self.confidence,
            "summary": self.summary,
            "reasoning": self.reasoning,
            "entities": [entity.to_dict() for entity in self.entities],
            "steps": [step.to_dict() for step in self.steps],
            "clarification_needed": self.clarification_needed,
            "clarification_question": self.clarification_question,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_reason": self.confirmation_reason,
            "diagnostics": self.diagnostics,
        }
