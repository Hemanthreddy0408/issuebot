"""The main agent loop."""

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from issuebot.agent.budget import Budget, BudgetExceeded
from issuebot.agent.context import build_overview
from issuebot.agent.loop_detector import LoopDetector
from issuebot.agent.prompts import NUDGE_MESSAGE, SYSTEM_PROMPT, build_task_message
from issuebot.agent.tools import TOOL_SCHEMAS, ToolError, ToolExecutor
from issuebot.llm.base import LLMClient, LLMResponse
from issuebot.models import RunResult, RunStatus, Step, Task, ToolCall, ToolResult
from issuebot.observability.cost import compute_cost
from issuebot.observability.tracing import Tracer
from issuebot.repo.workspace import Workspace

logger = logging.getLogger(__name__)


def _assistant_blocks(resp: LLMResponse) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if resp.text:
        blocks.append({"type": "text", "text": resp.text})
    for c in resp.tool_calls:
        blocks.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments})
    return blocks or [{"type": "text", "text": "(no output)"}]


def _tool_result_block(result: ToolResult) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": result.tool_call_id,
        "content": result.output or "(empty)",
        "is_error": not result.ok,
    }


def solve_task(
    task: Task,
    llm: LLMClient,
    *,
    tracer: Tracer | None = None,
    keep_workspace: bool = False,
    run_id: str | None = None,
) -> RunResult:
    """Run the agent on `task` and return a RunResult. Never modifies task.repo_path."""
    run_id = run_id or uuid.uuid4().hex[:12]
    tracer = tracer or Tracer(None)
    ws = Workspace.create(Path(task.repo_path))
    from issuebot.config import get_settings

    executor = ToolExecutor(ws, task.test_command, get_settings().test_timeout_seconds)
    budget = Budget(task.max_steps, task.max_cost_usd, task.max_wall_seconds)
    detector = LoopDetector()
    steps: list[Step] = []
    status = RunStatus.ERROR
    explanation: str | None = None

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": build_task_message(task, build_overview(ws))}
    ]
    tracer.log(event="run_start", run_id=run_id, task_id=task.task_id, model=llm.model)

    from issuebot.security.injection import detect_injection
    from issuebot.security.secrets import redact_secrets

    injection_check = detect_injection(f"{task.issue_title}\n{task.issue_body}")
    if injection_check.flagged:
        logger.warning(
            "Prompt injection patterns detected in task %s: %s",
            task.task_id,
            injection_check.details,
        )
        tracer.log(
            event="security_injection",
            task_id=task.task_id,
            patterns=injection_check.patterns,
            details=injection_check.details,
        )

    def log_step(
        call: ToolCall | None,
        result: ToolResult | None,
        resp: LLMResponse,
        cost: float,
        first: bool,
    ) -> None:
        step = Step(
            index=len(steps),
            llm_model=resp.model or llm.model,
            input_tokens=resp.input_tokens if first else 0,
            output_tokens=resp.output_tokens if first else 0,
            cost_usd=cost if first else 0.0,
            latency_ms=resp.latency_ms if first else 0,
            tool_call=call,
            tool_result=result,
            assistant_text=resp.text if first else None,
        )
        steps.append(step)
        tracer.log(
            event="step",
            cache_read_tokens=resp.cache_read_tokens if first else 0,
            cache_write_tokens=resp.cache_write_tokens if first else 0,
            **step.model_dump(mode="json"),
        )

    try:
        nudged = False
        failed_finishes = 0
        done = False
        while not done:
            budget.check()
            resp = llm.complete(SYSTEM_PROMPT, messages, TOOL_SCHEMAS)
            cost = compute_cost(
                resp.model or llm.model,
                resp.input_tokens,
                resp.output_tokens,
                resp.cache_read_tokens,
                resp.cache_write_tokens,
            )
            budget.record(resp.input_tokens, resp.output_tokens, cost)
            messages.append({"role": "assistant", "content": _assistant_blocks(resp)})

            if not resp.tool_calls:
                log_step(None, None, resp, cost, True)
                if nudged:
                    status = RunStatus.FAILED_TESTS
                    explanation = "The model stopped without calling a tool or finish."
                    break
                nudged = True
                messages.append({"role": "user", "content": NUDGE_MESSAGE})
                continue

            result_blocks: list[dict[str, Any]] = []
            for i, call in enumerate(resp.tool_calls):
                first = i == 0
                if detector.record_call(call.name, call.arguments):
                    log_step(call, None, resp, cost, first)
                    status = RunStatus.LOOP_DETECTED
                    explanation = f"Same {call.name} call repeated; aborting."
                    done = True
                    break

                if call.name == "finish":
                    summary = str(call.arguments.get("summary", ""))
                    try:
                        passed, test_summary = executor.run_tests_raw()
                    except ToolError as e:
                        passed, test_summary = False, f"ERROR: {e}"
                    if passed:
                        result = ToolResult(tool_call_id=call.id, ok=True, output=test_summary)
                        log_step(call, result, resp, cost, first)
                        status, explanation, done = RunStatus.SOLVED, summary, True
                        break
                    failed_finishes += 1
                    result = ToolResult(
                        tool_call_id=call.id,
                        ok=False,
                        output="Final verification FAILED; the tests do not pass.\n" + test_summary,
                    )
                    log_step(call, result, resp, cost, first)
                    if failed_finishes >= 2:
                        status, explanation, done = RunStatus.FAILED_TESTS, summary, True
                        break
                    result_blocks.append(_tool_result_block(result))
                    continue

                result = executor.execute(call)
                log_step(call, result, resp, cost, first)
                result_blocks.append(_tool_result_block(result))
                if call.name == "run_tests" and executor.last_test_passed is False:
                    tracer.log(event="raw_test_output", output=executor.last_raw_test_output)
                    if detector.record_test_failure(executor.last_test_digest, executor.edit_count):
                        status = RunStatus.LOOP_DETECTED
                        explanation = "Identical failing test output repeated with no edits."
                        done = True
                        break
            if not done:
                messages.append({"role": "user", "content": result_blocks})
    except BudgetExceeded as e:
        status, explanation = RunStatus.BUDGET_EXCEEDED, str(e)
    except Exception as e:
        logger.exception("Run %s crashed", run_id)
        status, explanation = RunStatus.ERROR, f"{type(e).__name__}: {e}"

    try:
        patch = ws.diff() or None
    except Exception:
        logger.exception("Failed to compute diff")
        patch = None

    clean_explanation = redact_secrets(explanation) if explanation else None
    clean_patch = redact_secrets(patch) if patch else None

    result_obj = RunResult(
        run_id=run_id,
        task_id=task.task_id,
        status=status,
        patch=clean_patch,
        steps=steps,
        total_input_tokens=budget.input_tokens,
        total_output_tokens=budget.output_tokens,
        total_cost_usd=budget.cost_usd,
        wall_seconds=time.monotonic() - budget.start,
        model_config_name=llm.model,
        explanation=clean_explanation,
    )
    tracer.log(event="run_end", status=status.value, cost_usd=budget.cost_usd)
    if not keep_workspace:
        ws.cleanup()
    return result_obj
