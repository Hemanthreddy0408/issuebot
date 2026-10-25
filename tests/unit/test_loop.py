from issuebot.agent.loop import solve_task
from issuebot.llm.mock import ScriptedLLM, make_response
from issuebot.models import RunStatus
from issuebot.observability.tracing import Tracer

FIX = (
    "edit_file",
    {"path": "cart.py", "old_str": "quantity > BULK", "new_str": "quantity >= BULK"},
)


def test_solves_seed_bug(task, tmp_path):
    llm = ScriptedLLM(
        [
            make_response("Look for the discount.", ("search_code", {"query": "BULK_THRESHOLD"})),
            make_response("Plan: change > to >=.", ("read_file", {"path": "cart.py"})),
            make_response(None, FIX),
            make_response(None, ("run_tests", {})),
            make_response(None, ("finish", {"summary": "Use >= for the bulk threshold."})),
        ]
    )
    trace = tmp_path / "trace.jsonl"
    r = solve_task(task, llm, tracer=Tracer(trace))
    assert r.status == RunStatus.SOLVED
    assert r.patch and "+        if item.quantity >= BULK_THRESHOLD:" in r.patch
    assert r.explanation == "Use >= for the bulk threshold."
    assert len(r.steps) == 5
    assert r.total_cost_usd > 0 and r.total_input_tokens == 500
    assert trace.read_text().count('"event": "step"') == 5
    # the original repo is never modified
    assert "quantity > BULK_THRESHOLD" in (task.repo_path / "cart.py").read_text()


def test_edit_before_explore_is_rejected_but_run_continues(task):
    llm = ScriptedLLM(
        [
            make_response(None, FIX),
            make_response(None, ("read_file", {"path": "cart.py"})),
            make_response(None, FIX),
            make_response(None, ("finish", {"summary": "done"})),
        ]
    )
    r = solve_task(task, llm)
    assert r.steps[0].tool_result and not r.steps[0].tool_result.ok
    assert r.status == RunStatus.SOLVED


def test_finish_without_passing_tests_is_not_solved(task):
    llm = ScriptedLLM(
        [
            make_response(None, ("finish", {"summary": "I think it works"})),
            make_response(None, ("finish", {"summary": "really"})),
        ]
    )
    r = solve_task(task, llm)
    assert r.status == RunStatus.FAILED_TESTS
    assert r.patch is None


def test_no_tool_call_twice_fails(task):
    llm = ScriptedLLM([make_response("hmm"), make_response("still thinking")])
    r = solve_task(task, llm)
    assert r.status == RunStatus.FAILED_TESTS
    assert len(llm.calls) == 2


def test_loop_detected(task):
    same = ("read_file", {"path": "cart.py"})
    llm = ScriptedLLM([make_response(None, same) for _ in range(5)])
    assert solve_task(task, llm).status == RunStatus.LOOP_DETECTED


def test_step_budget(task):
    task = task.model_copy(update={"max_steps": 2})
    llm = ScriptedLLM(
        [
            make_response(None, ("read_file", {"path": "cart.py"})),
            make_response(None, ("search_code", {"query": "total"})),
            make_response(None, ("git_diff", {})),
        ]
    )
    assert solve_task(task, llm).status == RunStatus.BUDGET_EXCEEDED


def test_cost_budget(task):
    task = task.model_copy(update={"max_cost_usd": 1e-9})
    llm = ScriptedLLM(
        [make_response(None, ("git_diff", {})), make_response(None, ("git_diff", {}))]
    )
    assert solve_task(task, llm).status == RunStatus.BUDGET_EXCEEDED


def test_llm_crash_becomes_error_status(task):
    llm = ScriptedLLM([])  # raises AssertionError on first call
    r = solve_task(task, llm)
    assert r.status == RunStatus.ERROR
