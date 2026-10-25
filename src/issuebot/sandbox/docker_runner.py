"""Docker-based sandbox runner for untrusted code execution."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_OUTPUT_CHARS = 50_000


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of executing a command inside the sandbox container."""

    exit_code: int
    output: str
    timed_out: bool = False


class DockerSandboxError(RuntimeError):
    """Raised when docker sandbox execution fails due to infrastructure errors."""


class DockerSandboxRunner:
    """Executes commands inside an isolated, resource-constrained Docker container."""

    def __init__(
        self,
        image: str = "issuebot-sandbox:latest",
        mem_limit: str = "512m",
        nano_cpus: int = 1_000_000_000,  # 1 CPU
        pids_limit: int = 128,
        timeout_seconds: int = 60,
    ) -> None:
        self.image = image
        self.mem_limit = mem_limit
        self.nano_cpus = nano_cpus
        self.pids_limit = pids_limit
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def is_docker_available() -> bool:
        """Check if Docker daemon is running and reachable."""
        try:
            import docker
            from docker.errors import DockerException

            client = docker.from_env()
            return bool(client.ping())
        except (DockerException, OSError, ImportError):
            return False

    def run(
        self,
        workspace_dir: Path,
        command: list[str],
        timeout: int | None = None,
    ) -> SandboxResult:
        """Execute `command` in an ephemeral container mounted with `workspace_dir`.

        Enforces Section 9.1:
        - network_mode="none"
        - read_only root filesystem with writable tmpfs on /tmp
        - workspace mounted at /workspace
        - non-root user (10001:10001)
        - memory, CPU, PID limits
        - cap_drop=["ALL"], security_opt=["no-new-privileges"]
        - hard wall-clock timeout
        - no environment variables passed
        - always removed in finally block
        """
        import docker
        from docker.errors import DockerException

        timeout_sec = timeout if timeout is not None else self.timeout_seconds
        abs_workspace = workspace_dir.resolve()

        try:
            client = docker.from_env()
        except (DockerException, OSError) as e:
            raise DockerSandboxError(f"Could not connect to Docker daemon: {e}") from e

        container = None
        start_time = time.monotonic()
        timed_out = False

        try:
            # Create and launch locked-down container
            container = client.containers.create(
                image=self.image,
                command=command,
                network_mode="none",
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
                volumes={str(abs_workspace): {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                user="10001:10001",
                mem_limit=self.mem_limit,
                nano_cpus=self.nano_cpus,
                pids_limit=self.pids_limit,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                environment={},  # Zero environment variables or secrets passed
                detach=True,
            )

            container.start()

            # Poll for completion with wall-clock timeout
            while True:
                container.reload()
                status = container.status
                if status in ("exited", "dead"):
                    break

                elapsed = time.monotonic() - start_time
                if elapsed >= timeout_sec:
                    timed_out = True
                    logger.warning(
                        "Sandbox container %s timed out after %ds; killing",
                        container.short_id,
                        timeout_sec,
                    )
                    try:
                        container.kill()
                    except (DockerException, OSError) as kill_err:
                        logger.warning("Error killing container: %s", kill_err)
                    break

                time.sleep(0.2)

            # Retrieve stdout/stderr logs
            raw_logs = b""
            try:
                raw_logs = container.logs(stdout=True, stderr=True)
            except (DockerException, OSError) as log_err:
                logger.warning("Could not fetch container logs: %s", log_err)

            output = raw_logs.decode("utf-8", errors="replace")

            if timed_out:
                exit_code = -1
                output = f"Execution timed out after {timeout_sec} seconds.\n" + output
            else:
                container.reload()
                exit_code = container.attrs.get("State", {}).get("ExitCode", 0)

            # Cap output length
            if len(output) > MAX_OUTPUT_CHARS:
                output = (
                    output[:MAX_OUTPUT_CHARS]
                    + f"\n[truncated {len(output) - MAX_OUTPUT_CHARS} characters]"
                )

            return SandboxResult(exit_code=exit_code, output=output, timed_out=timed_out)

        except DockerException as e:
            logger.exception("Docker sandbox execution error")
            raise DockerSandboxError(f"Docker container run failed: {e}") from e

        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except (DockerException, OSError) as rem_err:
                    logger.warning("Failed to remove container %s: %s", container.short_id, rem_err)
