"""Durable one-step plan runner for triple-comma autonomy."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from typing import Any

from .qwen import chat_json, ensure_server
from .security import create_trust_metadata
from .state import append_event, append_jsonl, read_jsonl
from .tty import prompt_on_tty

LAST_PLAN = "last-plan.jsonl"
MAX_PLAN_STEPS = 6
MAX_EVENT_OUTPUT_CHARS = 4000

PLAN_SYSTEM = (
    "You are a shell-native planning operator. Generate a short bounded plan "
    "made of concrete shell commands. Each step must be safe to run as one "
    "boxed shell command after user confirmation. Prefer inspection and tests "
    "before edits. Do not include prose outside the JSON fields."
)

PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_PLAN_STEPS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short imperative title for this step.",
                    },
                    "command": {
                        "type": "string",
                        "description": "Exactly one concrete shell command.",
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Why this step is useful now.",
                    },
                },
                "required": ["title", "command", "explanation"],
            },
        }
    },
    "required": ["steps"],
}


def run_plan_stepper(
    *,
    objective: str,
    stdin_text: str = "",
    dry_run: bool = False,
) -> int:
    """Create or resume a durable plan and handle at most one step."""
    plan = active_plan()
    if plan is None:
        if not objective:
            print("sigil plan: no active plan; provide an objective", file=sys.stderr)
            return 2
        if dry_run:
            print("sigil plan: would create a plan and propose the first step")
            return 0
        plan = create_plan(objective=objective, stdin_text=stdin_text)
    elif objective and objective != str(plan.get("objective", "")):
        if dry_run:
            print("sigil plan: would replace active plan with a new objective")
            return 0
        plan = create_plan(objective=objective, stdin_text=stdin_text)
    elif dry_run:
        print("sigil plan: would resume active plan and propose the next step")
        return 0

    print_plan(plan)
    step = next_pending_step(plan)
    if step is None:
        plan["status"] = "completed"
        record_plan_update("plan_completed", plan)
        print("plan complete")
        return 0

    print_next_step(step)
    decision = read_step_decision()
    if decision in {"", "n", "no", "quit", "q"}:
        return 0
    if decision == "skip":
        step["status"] = "skipped"
        record_step_decision(plan, step, "skipped")
        print(f"skipped step {step['id']}")
        return 0
    if decision == "edit":
        edited = prompt_on_tty("command> ")
        if edited is None or not edited.strip():
            return 0
        step["command"] = edited.strip()
        step["edited"] = True
        confirm = read_step_decision(prompt="run edited step? [y/N] ")
        if confirm not in {"y", "yes"}:
            return 0
    elif decision not in {"y", "yes"}:
        return 0

    record_step_decision(plan, step, "accepted")
    return execute_plan_step(plan, step)


def create_plan(*, objective: str, stdin_text: str = "") -> dict[str, Any]:
    """Generate and store a fresh active plan."""
    if not ensure_server():
        raise SystemExit(1)
    user = plan_user_prompt(objective, stdin_text)
    data = chat_json(PLAN_SYSTEM, user, PLAN_SCHEMA)
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise RuntimeError(",,, did not produce a plan")
    steps = []
    for index, raw_step in enumerate(raw_steps[:MAX_PLAN_STEPS], start=1):
        if not isinstance(raw_step, dict):
            continue
        title = str(raw_step.get("title", "")).strip()
        command = str(raw_step.get("command", "")).strip()
        explanation = str(raw_step.get("explanation", "")).strip()
        if not command:
            continue
        steps.append(
            {
                "id": str(index),
                "title": title or f"Step {index}",
                "command": command,
                "explanation": explanation,
                "status": "pending",
            }
        )
    if not steps:
        raise RuntimeError(",,, did not produce runnable plan steps")
    plan = {
        "plan_id": str(uuid.uuid4()),
        "objective": objective,
        "status": "active",
        "steps": steps,
    }
    record_plan_update("plan_created", plan)
    return plan


def plan_user_prompt(objective: str, stdin_text: str) -> str:
    """Build the model prompt for plan generation."""
    sections = [f"Objective: {objective}", f"Working directory: {os.getcwd()}"]
    if stdin_text:
        sections.append(f"Piped input:\n{stdin_text}")
    return "\n\n".join(sections)


def active_plan() -> dict[str, Any] | None:
    """Return the latest active plan snapshot for this session."""
    for event in reversed(read_jsonl(LAST_PLAN)):
        plan = event.get("plan")
        if isinstance(plan, dict):
            status = plan.get("status")
            if status == "active":
                return plan
            if status in {"aborted", "completed"}:
                return None
    return None


def last_plan() -> dict[str, Any] | None:
    """Return the latest plan snapshot for this session."""
    for event in reversed(read_jsonl(LAST_PLAN)):
        plan = event.get("plan")
        if isinstance(plan, dict):
            return plan
    return None


def abort_active_plan() -> dict[str, Any] | None:
    """Mark the active plan aborted."""
    plan = active_plan()
    if plan is None:
        return None
    plan["status"] = "aborted"
    record_plan_update("plan_aborted", plan)
    return plan


def next_pending_step(plan: dict[str, Any]) -> dict[str, Any] | None:
    """Return the next pending step in a plan."""
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return None
    for step in steps:
        if isinstance(step, dict) and step.get("status") == "pending":
            return step
    return None


def print_plan(plan: dict[str, Any]) -> None:
    """Print a compact plan overview."""
    steps = [step for step in plan.get("steps", []) if isinstance(step, dict)]
    print(f"plan ({len(steps)} steps):")
    for step in steps:
        status = str(step.get("status") or "pending")
        print(f"  {step.get('id')}. [{status}] {step.get('title')}")


def print_next_step(step: dict[str, Any]) -> None:
    """Print the next proposed step."""
    print("")
    print("next:")
    print(str(step.get("command") or ""))
    explanation = str(step.get("explanation") or "")
    if explanation:
        print(explanation)
    print("")


def read_step_decision(prompt: str = "proceed? [y/N/skip/edit/quit] ") -> str:
    """Read a plan-step decision from the terminal."""
    answer = prompt_on_tty(prompt)
    return "" if answer is None else answer.strip().lower()


def execute_plan_step(plan: dict[str, Any], step: dict[str, Any]) -> int:
    """Execute one accepted plan step and persist the result."""
    command = str(step.get("command") or "")
    result = execute_command(command)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    step["status"] = "done" if result.returncode == 0 else "failed"
    step["exit_code"] = result.returncode
    step["stdout_snippet"] = result.stdout[:MAX_EVENT_OUTPUT_CHARS]
    step["stderr_snippet"] = result.stderr[:MAX_EVENT_OUTPUT_CHARS]
    record_step_executed(plan, step, result)
    if result.returncode == 0 and next_pending_step(plan) is None:
        plan["status"] = "completed"
        record_plan_update("plan_completed", plan)
    return result.returncode


def execute_command(command: str) -> subprocess.CompletedProcess[str]:
    """Execute a plan step through the user's shell."""
    shell = os.environ.get("SHELL") or "/bin/sh"
    return subprocess.run(
        [shell, "-lc", command],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def record_plan_update(event_type: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Record a plan snapshot in session and global state."""
    inputs = []
    last_event_id = plan.get("last_event_id")
    if event_type != "plan_created" and isinstance(last_event_id, str):
        inputs.append(last_event_id)
    security = create_trust_metadata(
        glyph=",,,",
        integrity="local_model",
        capability="propose",
        taint=["model"],
        inputs=inputs,
        fresh_human=True,
    )
    payload = {
        "type": event_type,
        "plan_id": plan.get("plan_id"),
        "objective": plan.get("objective"),
        "plan": plan,
        **security,
    }
    global_event = append_event(payload)
    if event_type == "plan_created":
        plan["event_id"] = global_event["id"]
    plan["last_event_id"] = global_event["id"]
    payload["plan"] = plan
    session_event = append_jsonl(LAST_PLAN, payload)
    return session_event


def record_step_decision(
    plan: dict[str, Any],
    step: dict[str, Any],
    decision: str,
) -> dict[str, Any]:
    """Record a user decision for one plan step."""
    step["decision"] = decision
    inputs = []
    plan_event_id = plan.get("event_id")
    if isinstance(plan_event_id, str):
        inputs.append(plan_event_id)
    security = create_trust_metadata(
        glyph=",,,",
        integrity="human",
        capability="none",
        taint=[],
        inputs=inputs,
        fresh_human=True,
    )
    payload = {
        "type": "plan_step_decision",
        "plan_id": plan.get("plan_id"),
        "step_id": step.get("id"),
        "decision": decision,
        "command": step.get("command"),
        "plan": plan,
        **security,
    }
    global_event = append_event(payload)
    step["decision_event_id"] = global_event["id"]
    plan["last_event_id"] = global_event["id"]
    payload["decision_event_id"] = global_event["id"]
    payload["plan"] = plan
    session_event = append_jsonl(LAST_PLAN, payload)
    return session_event


def record_step_executed(
    plan: dict[str, Any],
    step: dict[str, Any],
    result: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    """Record one boxed command execution for a plan step."""
    inputs = []
    decision_event_id = step.get("decision_event_id")
    if isinstance(decision_event_id, str):
        inputs.append(decision_event_id)
    security = create_trust_metadata(
        glyph=",,,",
        integrity="local_model",
        capability="exec_boxed",
        taint=["model"],
        inputs=inputs,
        fresh_human=True,
    )
    payload = {
        "type": "plan_step_executed",
        "plan_id": plan.get("plan_id"),
        "step_id": step.get("id"),
        "command": step.get("command"),
        "status": result.returncode,
        "stdout_snippet": result.stdout[:MAX_EVENT_OUTPUT_CHARS],
        "stderr_snippet": result.stderr[:MAX_EVENT_OUTPUT_CHARS],
        "plan": plan,
        **security,
    }
    global_event = append_event(payload)
    step["execution_event_id"] = global_event["id"]
    plan["last_event_id"] = global_event["id"]
    payload["execution_event_id"] = global_event["id"]
    payload["plan"] = plan
    session_event = append_jsonl(LAST_PLAN, payload)
    return session_event
