"""Tiny test execution runner executed inside the locked-down Docker sandbox."""

import os
import subprocess
import sys

MAX_OUTPUT_BYTES = 50_000


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("ERROR: No command provided to sandbox runner", file=sys.stderr)
        sys.exit(2)

    # If first argument is 'pytest', run via python -m pytest
    if args[0] == "pytest":
        cmd = [sys.executable, "-m", "pytest", *args[1:]]
    elif args[:3] == ["python", "-m", "pytest"]:
        cmd = [sys.executable, "-m", "pytest", *args[3:]]
    elif args[0] == "python":
        cmd = [sys.executable, *args[1:]]
    else:
        cmd = args

    # Clean execution environment inside container
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/workspace",
        "HOME": "/tmp",
    }

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            cwd="/workspace",
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        output = proc.stdout or ""
        if len(output) > MAX_OUTPUT_BYTES:
            output = (
                output[:MAX_OUTPUT_BYTES]
                + f"\n[truncated {len(output) - MAX_OUTPUT_BYTES} characters]"
            )
        sys.stdout.write(output)
        sys.exit(proc.returncode)
    except (OSError, subprocess.SubprocessError) as e:
        sys.stderr.write(f"Runner execution failed: {type(e).__name__}: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
