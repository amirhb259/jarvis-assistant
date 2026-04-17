from __future__ import annotations

import re
from typing import Callable
from app.commands.registry import CommandRegistry
from app.core.models import BrainEntity, BrainPlan, BrainStep, CommandRequest, CommandResult
from app.services.entity_extractor_service import EntityExtractorService
from app.services.nlu_service import NLUService


EventSink = Callable[[str], None]


class JarvisBrainService:
    def __init__(
        self,
        config,
        nlu_service: NLUService,
        entity_extractor: EntityExtractorService,
        registry: CommandRegistry,
        logger,
    ) -> None:
        self.config = config
        self.nlu_service = nlu_service
        self.entity_extractor = entity_extractor
        self.registry = registry
        self.logger = logger

    def update_config(self, config) -> None:
        self.config = config
        self.nlu_service.update_config(config)
        self.entity_extractor.update_config(config)

    def handle_user_command(
        self,
        user_text: str,
        context: dict[str, object] | None,
        emit_event: EventSink | None = None,
    ) -> CommandRequest:
        return self.analyze_text(user_text, context=context, emit_event=emit_event)

    def analyze_text(
        self,
        text: str,
        context: dict[str, object] | None = None,
        emit_event: EventSink | None = None,
    ) -> CommandRequest:
        request = self._build_request(text, context or {})
        return self.plan_request(request, context=context or {}, emit_event=emit_event)

    def plan_request(
        self,
        request: CommandRequest,
        context: dict[str, object] | None = None,
        emit_event: EventSink | None = None,
    ) -> CommandRequest:
        event_sink = emit_event or (lambda _message: None)
        context_data = context or request.context_data or {}
        request.context_data = context_data

        selected_tool = ""
        steps = self._build_steps(request, context_data)
        if steps:
            selected_tool = steps[-1].tool_name or "compound_execution"
        else:
            handler = self.registry.get(request.intent)
            selected_tool = request.intent if handler else ""

        entities = self.entity_extractor.extract(request)
        plan = BrainPlan(
            intent=request.intent,
            selected_tool=selected_tool,
            confidence=request.confidence,
            entities=entities,
            steps=steps,
            clarification_needed=request.clarification_needed,
            clarification_question=request.clarification_question,
            diagnostics={
                "alternatives": request.alternatives,
                "context": context_data,
            },
        )

        if request.intent == "empty":
            plan.summary = "Kein verwertbarer Nutzerbefehl erkannt."
            plan.reasoning = "Die Eingabe war nach der Normalisierung leer."
        elif request.intent == "unknown":
            plan.summary = "Ich konnte die Absicht noch keinem internen Werkzeug zuordnen."
            plan.reasoning = "Kein Intent-Kandidat war stark genug."
        elif selected_tool == "":
            plan.summary = "Es wurde zwar eine Absicht erkannt, aber noch kein passendes internes Tool gefunden."
            plan.reasoning = "Für diesen Intent ist aktuell kein Handler registriert."
        else:
            plan.summary = self._build_summary(request, plan.steps, selected_tool)
            plan.reasoning = self._build_reasoning(request, selected_tool)
            plan.requires_confirmation = any(step.requires_confirmation for step in plan.steps)
            if plan.requires_confirmation:
                plan.confirmation_reason = "Mindestens ein geplanter Schritt ist als sensibel markiert."

        if request.clarification_needed and not plan.clarification_question:
            plan.clarification_question = "Kannst du kurz präzisieren, was du genau meinst?"

        request.plan = plan
        request.diagnostics = request.diagnostics | {"brain": plan.to_dict()}

        self.logger.info(
            "Brain planned intent=%s tool=%s confidence=%.2f entities=%s steps=%s",
            request.intent,
            selected_tool or "none",
            request.confidence,
            [(entity.kind, entity.value) for entity in entities],
            [(step.intent, step.tool_name) for step in steps],
        )
        event_sink(
            f"Brain selected {selected_tool or 'no tool'} for intent {request.intent} at confidence {request.confidence:.2f}"
        )
        if entities:
            event_sink("Extracted entities: " + ", ".join(f"{entity.kind}={entity.value}" for entity in entities))
        for step in plan.steps:
            event_sink(f"Planned step: {step.description}")
        return request

    def finalize_result(self, request: CommandRequest, result: CommandResult) -> CommandResult:
        plan = request.plan
        result.intent = result.intent or request.intent
        result.confidence = result.confidence or request.confidence
        result.selected_tool = result.selected_tool or (plan.selected_tool if plan else "")
        result.plan_summary = result.plan_summary or (plan.summary if plan else "")
        result.extracted_entities = result.extracted_entities or [entity.to_dict() for entity in (plan.entities if plan else [])]
        result.planned_steps = result.planned_steps or [step.to_dict() for step in (plan.steps if plan else [])]
        result.execution_status = self._execution_status(result)
        result.message = self._natural_response(request, result)
        if not result.spoken_text:
            result.spoken_text = result.message
        return result

    def _build_request(self, text: str, context: dict[str, object]) -> CommandRequest:
        compound = self._interpret_compound(text, context)
        if compound is not None:
            return compound
        return self.nlu_service.interpret(text, context=context)

    def _interpret_compound(self, text: str, context: dict[str, object]) -> CommandRequest | None:
        cleaned = text.strip()
        normalized = cleaned.lower()
        if not any(connector in normalized for connector in (" und ", " and ", " danach ", " then ")):
            return None

        if any(word in normalized for word in ("youtube",)) and any(word in normalized for word in ("such", "search", "finde")):
            query = self._extract_compound_search_query(cleaned)
            if query:
                return CommandRequest(
                    raw_text=text,
                    clean_text=cleaned,
                    normalized_text=normalized,
                    intent="search_youtube",
                    confidence=0.9,
                    slots={"query": query, "target": "YouTube"},
                    context_data=context,
                    diagnostics={"compound_reason": "open_youtube_then_search"},
                )

        if any(word in normalized for word in ("google", "browser")) and any(word in normalized for word in ("such", "search", "finde")):
            query = self._extract_compound_search_query(cleaned)
            if query:
                return CommandRequest(
                    raw_text=text,
                    clean_text=cleaned,
                    normalized_text=normalized,
                    intent="search_google",
                    confidence=0.84,
                    slots={"query": query, "target": "Google"},
                    context_data=context,
                    diagnostics={"compound_reason": "open_web_then_search"},
                )
        return None

    def _build_steps(self, request: CommandRequest, context: dict[str, object]) -> list[BrainStep]:
        handler = self.registry.get(request.intent)
        tool_name = request.intent if handler is not None else ""
        steps: list[BrainStep] = []

        if request.intent in {"empty", "unknown"} or handler is None and request.intent not in {"search_youtube", "search_google", "open_app"}:
            return steps

        if request.intent == "search_youtube" and request.diagnostics.get("compound_reason") == "open_youtube_then_search":
            steps.append(
                BrainStep(
                    description="Öffne zuerst YouTube im Browser.",
                    tool_name="open_website",
                    intent="open_website",
                    slots={"target": "youtube"},
                )
            )
            steps.append(
                BrainStep(
                    description=f"Führe danach die YouTube-Suche nach '{request.slots.get('query', '')}' aus.",
                    tool_name="search_youtube",
                    intent="search_youtube",
                    slots={"query": request.slots.get("query", "")},
                )
            )
            return steps

        if request.intent == "search_google" and request.diagnostics.get("compound_reason") == "open_web_then_search":
            browser_target = "google" if "google" in str(request.slots.get("target", "")).lower() else "google"
            steps.append(
                BrainStep(
                    description="Öffne zuerst den Browser bzw. Google.",
                    tool_name="open_website",
                    intent="open_website",
                    slots={"target": browser_target},
                )
            )
            steps.append(
                BrainStep(
                    description=f"Führe danach die Websuche nach '{request.slots.get('query', '')}' aus.",
                    tool_name="search_google",
                    intent="search_google",
                    slots={"query": request.slots.get("query", "")},
                )
            )
            return steps

        if request.intent == "open_app":
            target = str(request.slots.get("target", ""))
            steps.append(
                BrainStep(
                    description=f"Ermittle zuerst das beste installierte Programm für '{target}'.",
                    tool_name="AppLauncherService",
                    intent="resolve_app",
                    slots={"target": target},
                )
            )
            steps.append(
                BrainStep(
                    description=f"Starte anschließend '{target}' mit {tool_name}.",
                    tool_name="open_app",
                    intent=request.intent,
                    slots=request.slots,
                )
            )
            return steps

        if request.intent in {"shutdown_pc", "restart_pc", "lock_pc"}:
            steps.append(
                BrainStep(
                    description="Bestätige zuerst die sensible Systemaktion mit dem Nutzer.",
                    tool_name="ConfirmationDialog",
                    intent="confirm_sensitive_action",
                    requires_confirmation=True,
                )
            )

        steps.append(
            BrainStep(
                description=f"Führe den Intent '{request.intent}' mit {request.intent or 'dem passenden Tool'} aus.",
                tool_name=request.intent,
                intent=request.intent,
                slots=request.slots,
                requires_confirmation=bool(handler and handler.dangerous),
            )
        )

        if self._should_use_context_search(request, context):
            query = str(request.slots.get("query", ""))
            last_target = str(context.get("last_website") or context.get("last_target", ""))
            steps.insert(
                0,
                BrainStep(
                    description=f"Nutze den Kontext aus der letzten Anfrage ('{last_target}') für die Suche nach '{query}'.",
                    tool_name="ContextResolver",
                    intent="resolve_context_reference",
                    slots={"last_target": last_target, "query": query},
                )
            )
        return steps

    @staticmethod
    def _build_summary(request: CommandRequest, steps: list[BrainStep], selected_tool: str) -> str:
        if len(steps) > 1:
            return f"Ich plane {len(steps)} Schritte und nutze am Ende {selected_tool} für '{request.intent}'."
        target = request.slots.get("target") or request.slots.get("query") or request.slots.get("name") or ""
        if target:
            return f"Ich nutze {selected_tool}, um '{request.intent}' für '{target}' auszuführen."
        return f"Ich nutze {selected_tool}, um '{request.intent}' auszuführen."

    @staticmethod
    def _build_reasoning(request: CommandRequest, selected_tool: str) -> str:
        diagnostics = request.diagnostics.get("candidates", [])
        if diagnostics:
            top = diagnostics[0]
            return (
                f"Ausgewählt wurde {selected_tool}, weil der Intent '{request.intent}' mit {request.confidence:.2f} "
                f"über die Regel '{top.get('reason', 'unknown')}' erkannt wurde."
            )
        if request.diagnostics.get("compound_reason"):
            return f"Mehrschrittige Anfrage erkannt: {request.diagnostics['compound_reason']}."
        return f"Ausgewählt wurde {selected_tool}, weil es für '{request.intent}' registriert ist."

    @staticmethod
    def _extract_compound_search_query(text: str) -> str:
        query = re.sub(r".*?\b(?:such|suche|search|finde)\b", "", text, flags=re.IGNORECASE)
        query = re.sub(r"\b(dort|da|there|auf youtube|bei youtube|auf google|im browser|nach)\b", " ", query, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", query).strip(" .")

    @staticmethod
    def _should_use_context_search(request: CommandRequest, context: dict[str, object]) -> bool:
        if request.intent not in {"search_google", "search_youtube"}:
            return False
        if not (context.get("last_target") or context.get("last_website")):
            return False
        lowered = request.clean_text.lower()
        return any(token in lowered for token in ("dort", "da", "there")) or lowered.startswith(
            ("und ", "and ", "dann ", "danach ", "jetzt ", "nun ")
        )

    @staticmethod
    def _execution_status(result: CommandResult) -> str:
        if result.requires_confirmation:
            return "awaiting_confirmation"
        return "completed" if result.ok else "failed"

    def _natural_response(self, request: CommandRequest, result: CommandResult) -> str:
        if result.requires_confirmation:
            reason = request.plan.confirmation_reason if request.plan else "Die Aktion ist sensibel."
            return f"Bevor ich das ausführe, brauche ich eine Bestätigung. {reason}"

        if request.clarification_needed:
            return request.clarification_question or "Ich bin mir nicht ganz sicher, was du meinst."

        if not result.ok:
            if result.suggestions:
                return f"{result.message} Vielleicht meintest du: {', '.join(result.suggestions)}."
            return result.message

        intent = request.intent
        if intent == "open_app":
            target = result.understood_target or str(request.slots.get("target", ""))
            return f"Ich öffne jetzt {target}."
        if intent == "open_website":
            target = result.understood_target or str(request.slots.get("target", ""))
            return f"Ich öffne jetzt {target} im Browser."
        if intent == "search_youtube":
            return f"Ich suche jetzt auf YouTube nach {request.slots.get('query', '')}."
        if intent == "search_google":
            return f"Ich suche jetzt im Web nach {request.slots.get('query', '')}."
        if intent == "create_folder":
            return (
                f"Ich habe den Ordner {request.slots.get('name', '')} unter "
                f"{request.slots.get('location', '')} erstellt."
            )
        if intent == "create_file":
            return (
                f"Ich habe die Datei {request.slots.get('name', '')} unter "
                f"{request.slots.get('location', '')} erstellt."
            )
        if intent == "take_screenshot":
            return "Ich habe einen Screenshot aufgenommen."
        if intent == "tell_time":
            time_text = result.message.removeprefix("The time is ").rstrip(".")
            return f"Es ist jetzt {time_text}."
        if intent == "tell_date":
            date_text = result.message.removeprefix("Today is ").rstrip(".")
            return f"Heute ist {date_text}."
        if intent in {"volume_up", "volume_down", "set_volume", "mute_volume", "unmute_volume"}:
            return "Ich habe die Lautstärke entsprechend angepasst."
        if intent in {"shutdown_pc", "restart_pc"}:
            return result.message
        if intent == "lock_pc":
            return "Ich sperre jetzt den PC."
        if intent == "cancel_system_action":
            return "Ich habe die geplante Systemaktion abgebrochen."
        if intent == "type_text":
            return "Ich tippe den gewünschten Text jetzt ein."
        if intent in {"move_mouse", "click_mouse"}:
            return result.message
        if intent == "focus_window":
            return f"Ich habe jetzt das Fenster '{result.understood_target or request.slots.get('target', '')}' nach vorn geholt."
        if intent == "clipboard_read":
            return "Ich habe den aktuellen Inhalt der Zwischenablage gelesen."
        if intent == "clipboard_write":
            return "Ich habe den Text in die Zwischenablage kopiert."
        return result.message
