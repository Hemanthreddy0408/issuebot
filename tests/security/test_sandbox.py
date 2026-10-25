"""Security tests for Docker sandbox isolation, resource limits, and network blocking."""

import pytest

from issuebot.sandbox.docker_runner import DockerSandboxRunner


@pytest.fixture
def sandbox_runner():
    runner = DockerSandboxRunner(image="issuebot-sandbox:latest", timeout_seconds=10)
    if not runner.is_docker_available():
        pytest.skip("Docker daemon is not available")
    return runner


def test_sandbox_no_network(sandbox_runner, tmp_path):
    """Verify Section 9.7: The sandbox container has no network access."""
    # Create a test script that attempts to open a network socket
    test_file = tmp_path / "test_network.py"
    test_file.write_text(
        """
import socket
import pytest

def test_outbound_connection():
    # Attempting to connect to external DNS should immediately fail
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect(("8.8.8.8", 53))
        # If we reach here, connection succeeded (security failure!)
        assert False, "Network connection succeeded in sandbox!"
    except OSError as e:
        # Expected: Network is unreachable
        pass
    finally:
        s.close()
"""
    )

    res = sandbox_runner.run(tmp_path, ["pytest", "-q", "test_network.py"])
    # The test verifying network is blocked should PASS (exit code 0)
    assert res.exit_code == 0
    assert "1 passed" in res.output or "passed" in res.output.lower()


def test_sandbox_read_only_root_filesystem(sandbox_runner, tmp_path):
    """Verify that root filesystem is mounted read-only and writes outside /tmp fail."""
    test_file = tmp_path / "test_readonly.py"
    test_file.write_text(
        """
import pytest

def test_root_is_readonly():
    with pytest.raises(OSError):
        with open("/etc/test_write.txt", "w") as f:
            f.write("malicious")

def test_tmp_is_writable():
    # /tmp tmpfs should be writable
    with open("/tmp/temp.txt", "w") as f:
        f.write("temporary data")
    with open("/tmp/temp.txt", "r") as f:
        assert f.read() == "temporary data"
"""
    )

    res = sandbox_runner.run(tmp_path, ["pytest", "-q", "test_readonly.py"])
    assert res.exit_code == 0
    assert "passed" in res.output.lower()


def test_sandbox_runs_as_non_root(sandbox_runner, tmp_path):
    """Verify that execution runs as a non-root user (UID 10001)."""
    test_file = tmp_path / "test_user.py"
    test_file.write_text(
        """
import os

def test_uid_is_non_root():
    uid = os.getuid()
    assert uid != 0, f"Running as root UID: {uid}"
    assert uid == 10001, f"Expected UID 10001, got {uid}"
"""
    )

    res = sandbox_runner.run(tmp_path, ["pytest", "-q", "test_user.py"])
    assert res.exit_code == 0
    assert "passed" in res.output.lower()


def test_sandbox_timeout_kills_container(sandbox_runner, tmp_path):
    """Verify that execution exceeding timeout is terminated."""
    test_file = tmp_path / "test_hang.py"
    test_file.write_text(
        """
import time

def test_hang():
    time.sleep(20)
"""
    )

    # Run with 2 second timeout
    res = sandbox_runner.run(tmp_path, ["pytest", "-q", "test_hang.py"], timeout=2)
    assert res.timed_out
    assert res.exit_code == -1
    assert "timed out" in res.output.lower()
