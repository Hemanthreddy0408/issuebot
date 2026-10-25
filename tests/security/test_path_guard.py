"""Security tests for PathGuard: workspace boundary enforcement and test integrity."""

import os

import pytest

from issuebot.agent.tools import ToolExecutor
from issuebot.models import ToolCall
from issuebot.repo.workspace import Workspace
from issuebot.security.path_guard import PathGuard, PathGuardError


@pytest.fixture
def ws_fixture(seed_repo):
    ws = Workspace.create(seed_repo)
    yield ws
    ws.cleanup()


def test_path_escape_traversal_rejected(ws_fixture):
    guard = PathGuard(ws_fixture.root)
    with pytest.raises(PathGuardError, match="escapes workspace"):
        guard.resolve_safe("../../etc/passwd")

    with pytest.raises(PathGuardError, match="escapes workspace"):
        guard.resolve_safe("sub/../../../etc/shadow")


def test_absolute_path_rejected(ws_fixture):
    guard = PathGuard(ws_fixture.root)
    with pytest.raises(PathGuardError, match="Absolute paths are forbidden"):
        guard.resolve_safe("/etc/passwd")

    with pytest.raises(PathGuardError, match="Absolute paths are forbidden"):
        guard.resolve_safe("/workspace/cart.py")


def test_symlink_escape_rejected(ws_fixture, tmp_path):
    guard = PathGuard(ws_fixture.root)
    outside_file = tmp_path / "sensitive.txt"
    outside_file.write_text("classified")

    evil_symlink = ws_fixture.root / "evil_link"
    try:
        os.symlink(outside_file, evil_symlink)
    except OSError:
        pytest.skip("Symlink creation not permitted in this environment")

    with pytest.raises(PathGuardError, match="escapes workspace"):
        guard.resolve_safe("evil_link")


def test_writing_to_protected_directories_rejected(ws_fixture):
    guard = PathGuard(ws_fixture.root)
    # .git/
    with pytest.raises(PathGuardError, match="Modifying files in '.git/' is prohibited"):
        guard.resolve_safe(".git/config", for_write=True)

    # hidden_tests/
    with pytest.raises(PathGuardError, match="Modifying files in 'hidden_tests/' is prohibited"):
        guard.resolve_safe("hidden_tests/test_secret.py", for_write=True)


def test_deleting_existing_assertions_blocked(ws_fixture):
    ex = ToolExecutor(ws_fixture, "pytest -q", use_docker=False)
    ex.execute(ToolCall(id="1", name="read_file", arguments={"path": "tests/test_cart.py"}))

    original = (ws_fixture.root / "tests/test_cart.py").read_text()
    assert "assert" in original

    # Attempt to replace assertion with 'pass' (weakening tests)
    res = ex.execute(
        ToolCall(
            id="2",
            name="edit_file",
            arguments={
                "path": "tests/test_cart.py",
                "old_str": "assert c.total() == 19.80",
                "new_str": "pass",
            },
        )
    )
    assert not res.ok
    assert "weakening assertions" in res.output.lower() or "prohibited" in res.output.lower()


def test_deleting_test_function_blocked(ws_fixture):
    guard = PathGuard(ws_fixture.root)
    old_test = "def test_a():\n    assert 1 == 1\n\ndef test_b():\n    assert 2 == 2\n"
    new_test = "def test_a():\n    assert 1 == 1\n"  # deleted test_b

    with pytest.raises(PathGuardError, match="Deleting or renaming existing test functions"):
        guard.validate_test_integrity(
            ws_fixture.root / "tests/test_sample.py", old_test, new_test
        )


def test_adding_new_test_function_and_assertion_allowed(ws_fixture):
    guard = PathGuard(ws_fixture.root)
    old_test = "def test_a():\n    assert 1 == 1\n"
    new_test = "def test_a():\n    assert 1 == 1\n\ndef test_b():\n    assert 2 == 2\n"

    # Should not raise
    guard.validate_test_integrity(ws_fixture.root / "tests/test_sample.py", old_test, new_test)
