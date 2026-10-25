"""Pydantic data models shared across IssueBot."""

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class Task(BaseModel):
    """A bug-fixing task."""

    task_id: str
    repo_path: Path
    issue_title: str
    issue_body: str
    test_command: str = "pytest -x -q"
    hidden_test_command: str | None = None
    max_steps: int = 25
    max_cost_usd: float = 0.50
    max_wall_seconds: int = 600


class ToolCall(BaseModel):
    """A tool invocation requested by the model.

    `name` is a plain str (not a Literal) so a hallucinated tool name becomes a
    recoverable tool error instead of a validation crash.
    """

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result of executing a tool call."""

    tool_call_id: str
    ok: bool
    output: str
    truncated: bool = False


class Step(BaseModel):
    """One recorded agent step (one tool call)."""

    index: int
    llm_model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    tool_call: ToolCall | None
    tool_result: ToolResult | None
    assistant_text: str | None


class RunStatus(str, Enum):
    """Terminal status of a run."""

    SOLVED = "solved"
    FAILED_TESTS = "failed_tests"
    BUDGET_EXCEEDED = "budget_exceeded"
    LOOP_DETECTED = "loop_detected"
    ERROR = "error"
    BLOCKED = "blocked_by_security"


class RunResult(BaseModel):
    """Full outcome of an agent run."""

    model_config = ConfigDict(protected_namespaces=())

    run_id: str
    task_id: str
    status: RunStatus
    patch: str | None
    steps: list[Step]
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    wall_seconds: float
    model_config_name: str
    explanation: str | None
    hidden_tests_passed: bool | None = None
