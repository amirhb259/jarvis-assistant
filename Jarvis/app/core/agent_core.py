from __future__ import annotations

from typing import Any, Callable

from app.commands.base import ActionContext
from app.commands.registry import CommandRegistry
from app.core.guardrails import Guardrails
from app.core.models import CommandRequest, CommandResult
from app.core.specialist_agents import BrowserAgent, DesktopAgent, FileSystemAgent, ResponseAgent, SystemControlAgent
from app.core.tool_registry import ToolDefinition, ToolRegistry
from app.services.brain_service import JarvisBrainService
from app.services.conversation_context_service import ConversationContextService


EventSink = Callable[[str], None]


class AgentCore:
    def __init__(
        self,
        config,
        brain: JarvisBrainService,
        command_registry: CommandRegistry,
        tool_registry: ToolRegistry,
        context_memory: ConversationContextService,
        guardrails: Guardrails,
        logger,
    ) -> None:
        self.config = config
        self.brain = brain
        self.command_registry = command_registry
        self.tool_registry = tool_registry
        self.context_memory = context_memory
        self.guardrails = guardrails
        self.logger = logger
        self.specialists = (
            DesktopAgent(),
            BrowserAgent(),
            FileSystemAgent(),
            SystemControlAgent(),
            ResponseAgent(),
        )

    def update_config(self, config) -> None:
        self.config = config
        self.brain.update_config(config)
        self.guardrails.update_config(config)

    def handle_user_command(
        self,
        user_text: str,
        action_context: ActionContext,
        context: dict[str, Any] | None = None,
        emit_event: EventSink | None = None,
        confirmed: bool = False,
    ) -> CommandResult:
        request = self.detect_intent(user_text, context or {}, emit_event=emit_event)
        return self.execute_request(request, action_context, context=context, emit_event=emit_event, confirmed=confirmed)

    def detect_intent(
        self,
        user_text: str,
        context: dict[str, Any] | None,
        emit_event: EventSink | None = None,
    ) -> CommandRequest:
        return self.brain.handle_user_command(user_text, context or {}, emit_event=emit_event)

    def extract_entities(self, request: CommandRequest) -> list[dict[str, Any]]:
        plan = request.plan
        return [entity.to_dict() for entity in (plan.entities if plan else [])]

    def build_action_plan(self, request: CommandRequest) -> list[dict[str, Any]]:
        plan = request.plan
        return [step.to_dict() for step in (plan.steps if plan else [])]

    def select_tool(self, plan_step: dict[str, Any], context: dict[str, Any] | None = None) -> ToolDefinition | None:
        del context
        intent = str(plan_step.get("intent", ""))
        if intent in {"resolve_app", "resolve_context_reference", "confirm_sensitive_action"}:
            return None
        return self.tool_registry.tool_for_intent(intent)

    def run_safety_check(
        self,
        tool_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ):
        tool = self.tool_registry.get(tool_name)
        return self.guardrails.run_safety_check(tool, params, context=context)

    def execute_tool(
        self,
        tool_name: str,
        request: CommandRequest,
        action_context: ActionContext,
    ) -> CommandResult:
        tool = self.tool_registry.get(tool_name)
        if tool is None:
            raise RuntimeError(f"Tool '{tool_name}' ist nicht registriert.")

        valid, message = tool.validate(request.slots)
        if not valid:
            return CommandResult(
                ok=False,
                message=message or f"Die Eingaben für Tool '{tool_name}' sind ungültig.",
                intent=request.intent,
                confidence=request.confidence,
                selected_tool=tool_name,
                execution_status="validation_failed",
            )

        try:
            return tool.executor(request, action_context)
        except Exception as exc:
            self.logger.exception("Tool execution failed for %s", tool_name)
            return CommandResult(
                ok=False,
                message=f"Die Aktion '{tool_name}' konnte nicht sauber ausgeführt werden: {exc}",
                intent=request.intent,
                confidence=request.confidence,
                selected_tool=tool_name,
                execution_status="execution_failed",
            )

    def execute_request(
        self,
        request: CommandRequest,
        action_context: ActionContext,
        context: dict[str, Any] | None = None,
        emit_event: EventSink | None = None,
        confirmed: bool = False,
    ) -> CommandResult:
        event_sink = emit_event or (lambda _message: None)
        context_data = context or request.context_data or {}
        entities = self.extract_entities(request)
        plan = self.build_action_plan(request)
        selected_tools: list[str] = []
        safety_flags: list[str] = []

        if request.intent == "empty":
            result = CommandResult(ok=False, message="Bitte gib einen Befehl ein.", intent=request.intent)
            return self._finalize(request, result, entities, plan, selected_tools, safety_flags)

        if request.intent == "unknown":
            result = CommandResult(
                ok=False,
                message="Ich konnte deine Anfrage noch keiner Fähigkeit zuordnen.",
                intent=request.intent,
                confidence=request.confidence,
            )
            return self._finalize(request, result, entities, plan, selected_tools, safety_flags)

        if request.clarification_needed:
            result = CommandResult(
                ok=False,
                message=request.clarification_question or "Kannst du kurz präzisieren, was du meinst?",
                intent=request.intent,
                confidence=request.confidence,
                execution_status="needs_clarification",
            )
            return self._finalize(request, result, entities, plan, selected_tools, safety_flags)

        executable_steps = [step for step in plan if step["intent"] not in {"resolve_app", "resolve_context_reference", "confirm_sensitive_action"}]
        if not executable_steps:
            executable_steps = [{"intent": request.intent, "tool_name": request.plan.selected_tool if request.plan else "", "slots": request.slots}]

        latest_result: CommandResult | None = None
        for step in executable_steps:
            tool = self.select_tool(step, context=context_data)
            if tool is None:
                continue
            selected_tools.append(tool.name)
            decision = self.run_safety_check(tool.name, dict(step.get("slots", {})), context=context_data)
            safety_flags.extend(decision.safety_flags)
            event_sink(
                f"Tool selection: {tool.name} via {tool.specialist or 'general'} | confirmation={decision.requires_confirmation}"
            )
            if decision.allowed is False:
                latest_result = CommandResult(
                    ok=False,
                    message=decision.message or "Diese Aktion wurde vom Sicherheitslayer blockiert.",
                    intent=str(step.get("intent", request.intent)),
                    confidence=request.confidence,
                    selected_tool=tool.name,
                    safety_flags=decision.safety_flags,
                    execution_status="blocked",
                )
                break
            if decision.requires_confirmation and not confirmed:
                latest_result = CommandResult(
                    ok=False,
                    message="Bestätigung erforderlich.",
                    intent=str(step.get("intent", request.intent)),
                    confidence=request.confidence,
                    requires_confirmation=True,
                    confirmation_title="Bestätigung erforderlich",
                    confirmation_message=decision.message or "Diese Aktion ist potenziell sensibel. Möchtest du fortfahren?",
                    pending_request=request,
                    selected_tool=tool.name,
                    safety_flags=decision.safety_flags,
                    execution_status="awaiting_confirmation",
                )
                break

            step_request = CommandRequest(
                raw_text=request.raw_text,
                clean_text=request.clean_text,
                normalized_text=request.normalized_text,
                intent=str(step.get("intent", request.intent)),
                confidence=request.confidence,
                slots=dict(step.get("slots", request.slots)),
                alternatives=request.alternatives,
                clarification_needed=False,
                clarification_question="",
                diagnostics=request.diagnostics,
                plan=request.plan,
                context_data=request.context_data,
            )
            latest_result = self.execute_tool(tool.name, step_request, action_context)
            if not latest_result.ok:
                break

        if latest_result is None:
            latest_result = CommandResult(ok=False, message="Es wurde kein auszuführender Schritt gefunden.", execution_status="failed")

        finalized = self._finalize(request, latest_result, entities, plan, selected_tools, safety_flags)
        self.update_memory(context_data, finalized)
        return finalized

    def generate_response(self, execution_result: CommandResult, context: dict[str, Any] | None = None) -> str:
        del context
        return execution_result.response_message or execution_result.message

    def update_memory(self, context: dict[str, Any] | None, result: CommandResult) -> None:
        del context
        self.context_memory.update_from_result(result)

    def _finalize(
        self,
        request: CommandRequest,
        result: CommandResult,
        entities: list[dict[str, Any]],
        plan: list[dict[str, Any]],
        selected_tools: list[str],
        safety_flags: list[str],
    ) -> CommandResult:
        result = self.brain.finalize_result(request, result)
        if selected_tools:
            result.selected_tool = selected_tools[-1]
        result.selected_tools = selected_tools or ([result.selected_tool] if result.selected_tool else [])
        result.extracted_entities = result.extracted_entities or entities
        result.planned_steps = result.planned_steps or plan
        result.safety_flags = sorted(dict.fromkeys(result.safety_flags + safety_flags))
        result.response_message = result.message
        result.agent_trace = {
            "raw_input": request.raw_text,
            "normalized_input": request.normalized_text,
            "detected_intent": result.intent,
            "confidence": result.confidence,
            "entities": result.extracted_entities,
            "plan": result.planned_steps,
            "selected_tool": result.selected_tool,
            "selected_tools": result.selected_tools,
            "requires_confirmation": result.requires_confirmation,
            "safety_flags": result.safety_flags,
            "execution_result": {
                "ok": result.ok,
                "status": result.execution_status,
                "message": result.message,
            },
            "natural_response": result.response_message,
        }
        result.diagnostics = result.diagnostics | {"agent_trace": result.agent_trace}
        return result
