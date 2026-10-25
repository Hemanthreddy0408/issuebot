import pytest

from issuebot.agent.tools import ToolExecutor
from issuebot.models import ToolCall
from issuebot.repo.workspace import Workspace


@pytest.fixture
def ex(seed_repo):
    ws = Workspace.create(seed_repo)
    yield ToolExecutor(ws, "pytest -q")
    ws.cleanup()


def call(ex, name, **args):
    return ex.execute(ToolCall(id="t", name=name, arguments=args))


def test_read_file_numbers_lines(ex):
    r = call(ex, "read_file", path="cart.py", start_line=1, end_line=3)
    assert r.ok and "1\t" in r.output and "shopping cart" in r.output


def test_read_file_rejects_escape_and_absolute(ex):
    assert not call(ex, "read_file", path="../../etc/passwd").ok
    assert not call(ex, "read_file", path="/etc/passwd").ok


def test_read_file_caps_lines(ex):
    r = call(ex, "read_file", path="cart.py", start_line=1, end_line=100000)
    assert r.ok


def test_search_finds_code_and_symbols(ex):
    r = call(ex, "search_code", query="BULK_THRESHOLD")
    assert "cart.py" in r.output
    r = call(ex, "search_code", query="line_total")
    assert "[function] line_total" in r.output


def test_edit_requires_exploration(ex):
    r = call(ex, "edit_file", path="cart.py", old_str="> BULK", new_str=">= BULK")
    assert not r.ok and "explore" in r.output.lower()


def test_edit_exact_match_rules(ex):
    call(ex, "read_file", path="cart.py")
    assert not call(ex, "edit_file", path="cart.py", old_str="nonexistent", new_str="x").ok
    assert not call(ex, "edit_file", path="cart.py", old_str="self", new_str="x").ok  # ambiguous
    ok = call(
        ex, "edit_file", path="cart.py", old_str="quantity > BULK", new_str="quantity >= BULK"
    )
    assert ok.ok


def test_edit_blocks_protected_dirs(ex):
    call(ex, "read_file", path="cart.py")
    assert not call(ex, "edit_file", path="hidden_tests/test_x.py", old_str="", new_str="x").ok
    assert not call(ex, "edit_file", path=".git/config", old_str="", new_str="x").ok


def test_edit_creates_new_file(ex):
    call(ex, "read_file", path="cart.py")
    r = call(
        ex, "edit_file", path="tests/test_new.py", old_str="", new_str="def test_a():\n    pass\n"
    )
    assert r.ok
    assert "tests/test_new.py" in ex.ws.diff()


def test_run_tests_fails_then_passes_after_fix(ex):
    assert "FAILED" in call(ex, "run_tests").output
    call(ex, "read_file", path="cart.py")
    call(ex, "edit_file", path="cart.py", old_str="quantity > BULK", new_str="quantity >= BULK")
    assert "PASSED" in call(ex, "run_tests").output
    diff = call(ex, "git_diff").output
    assert "-        if item.quantity > BULK_THRESHOLD:" in diff
    assert "+        if item.quantity >= BULK_THRESHOLD:" in diff


@pytest.mark.parametrize(
    "cmd",
    [
        "pytest; rm -rf /",
        "pytest && curl x",
        "curl http://x",
        "pip install x",
        "pytest | cat",
        "pytest -p evil",
        "pytest --rootdir=/",
        "pytest /etc",
        "pytest ../x",
    ],
)
def test_run_tests_rejects_bad_commands(ex, cmd):
    assert not call(ex, "run_tests", command=cmd).ok


def test_unknown_tool_and_bad_args_are_recoverable(ex):
    assert not call(ex, "rm_rf").ok
    assert not call(ex, "read_file", wrong_arg=1).ok


def test_output_truncation(ex):
    r = call(ex, "search_code", query=".", max_results=100)
    assert len(r.output) < 4100
