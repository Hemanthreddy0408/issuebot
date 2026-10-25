"""Command policy enforcement: allowlist for test execution commands."""

import shlex

SHELL_METACHARACTERS = set(";&|`$<>\n\r()\\*?!")

DENIED_COMMAND_KEYWORDS = {
    "curl",
    "wget",
    "pip",
    "rm",
    "sudo",
    "ssh",
    "nc",
    "netcat",
    "bash",
    "sh",
    "zsh",
    "cat",
    "eval",
    "exec",
    "chmod",
    "chown",
    "kill",
    "pkill",
    "touch",
    "mkdir",
    "cp",
    "mv",
}

DENIED_PYTEST_FLAGS = {
    "-p",
    "-c",
    "-o",
    "--rootdir",
    "--confcutdir",
    "--basetemp",
    "--import-mode",
    "--override-ini",
    "--pastebin",
}


class CommandPolicyError(ValueError):
    """Raised when a command violates the security command policy."""


class CommandPolicy:
    """Validates and parses test commands against a strict allowlist."""

    @staticmethod
    def validate_and_parse(command: str, test_path: str = "") -> list[str]:
        """Validate command syntax and arguments.

        Returns the tokenized argument list for pytest.
        Raises CommandPolicyError if the command violates security constraints.
        """
        if not command or not command.strip():
            raise CommandPolicyError("Empty test command")

        # Check for shell metacharacters
        for char in command:
            if char in SHELL_METACHARACTERS:
                raise CommandPolicyError(
                    f"Shell metacharacters are prohibited in test commands: {char!r}"
                )

        try:
            tokens = shlex.split(command)
        except ValueError as e:
            raise CommandPolicyError(f"Could not parse command string: {e}") from e

        if not tokens:
            raise CommandPolicyError("No tokens in command")

        # Check for banned keywords
        for token in tokens:
            lower_token = token.lower()
            if lower_token in DENIED_COMMAND_KEYWORDS:
                raise CommandPolicyError(
                    f"Forbidden command keyword {token!r} detected in test command"
                )

        # Allowlist matching: must begin with `pytest` or `python -m pytest`
        if tokens[0] == "pytest":
            args = tokens[1:]
        elif tokens[:3] == ["python", "-m", "pytest"]:
            args = tokens[3:]
        else:
            raise CommandPolicyError(
                "Only `pytest ...` or `python -m pytest ...` commands are allowed"
            )

        # Inspect pytest arguments
        for arg in args:
            # Check for path traversal or absolute paths in arguments
            if arg.startswith("/") or ".." in arg:
                raise CommandPolicyError(
                    f"Absolute paths and directory traversal ('..') are prohibited: {arg!r}"
                )

            # Check denied pytest flags
            flag_name = arg.split("=")[0]
            if flag_name in DENIED_PYTEST_FLAGS:
                raise CommandPolicyError(f"Pytest flag {flag_name!r} is prohibited for security")

        result = ["pytest", *args]
        if test_path:
            clean_path = test_path.strip()
            if clean_path.startswith("/") or ".." in clean_path:
                raise CommandPolicyError(
                    f"Invalid test path '{clean_path}': path traversal or absolute path"
                )
            result.append(clean_path)

        # Always disable external cache provider plugins for deterministic isolation
        result.extend(["-p", "no:cacheprovider"])
        return result
