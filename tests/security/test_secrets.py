"""Security tests for secrets redaction in logs, tool outputs, and traces."""

from issuebot.agent.tools import ToolExecutor
from issuebot.models import ToolCall
from issuebot.repo.workspace import Workspace
from issuebot.security.secrets import REDACTION_MARKER, redact_secrets


def test_redacts_anthropic_api_keys():
    text = "Failed with key sk-ant-api03-abcdef12345678901234567890_ABCD in response."
    redacted = redact_secrets(text)
    assert "sk-ant-" not in redacted
    assert REDACTION_MARKER in redacted


def test_redacts_openai_api_keys():
    text = "OpenAI key: sk-proj-1234567890abcdef1234567890abcdef1234567890"
    redacted = redact_secrets(text)
    assert "sk-proj-" not in redacted
    assert REDACTION_MARKER in redacted


def test_redacts_github_tokens():
    text_pat = "GitHub Token: ghp_1234567890abcdef1234567890abcdef1234"
    redacted_pat = redact_secrets(text_pat)
    assert "ghp_" not in redacted_pat
    assert REDACTION_MARKER in redacted_pat

    text_fine = "GitHub fine-grained: github_pat_11AABBCC0011223344556677889900AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQRR"
    redacted_fine = redact_secrets(text_fine)
    assert "github_pat_" not in redacted_fine
    assert REDACTION_MARKER in redacted_fine


def test_redacts_aws_and_private_keys():
    text_aws = "AWS credentials: AKIAIOSFODNN7EXAMPLE"
    assert REDACTION_MARKER in redact_secrets(text_aws)
    assert "AKIAIOSFODNN7EXAMPLE" not in redact_secrets(text_aws)

    text_key = (
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Y...\n-----END RSA PRIVATE KEY-----"
    )
    assert REDACTION_MARKER in redact_secrets(text_key)
    assert "MIIEowIBAAKCAQEA0Y" not in redact_secrets(text_key)


def test_custom_secret_redaction():
    custom_secret = "super_secret_internal_pass_987"
    text = f"The secret password is {custom_secret} for db."
    redacted = redact_secrets(text, custom_secrets=[custom_secret])
    assert custom_secret not in redacted
    assert REDACTION_MARKER in redacted


def test_tool_executor_redacts_secrets_in_tool_output(seed_repo):
    ws = Workspace.create(seed_repo)
    ex = ToolExecutor(ws, "pytest -q", use_docker=False)
    # Write a fake secret into a file in workspace
    (ws.root / "config.txt").write_text("API_KEY=sk-ant-api03-secret12345678901234567890")

    # Read the file through ToolExecutor
    res = ex.execute(ToolCall(id="1", name="read_file", arguments={"path": "config.txt"}))
    assert res.ok
    assert "sk-ant-api03" not in res.output
    assert REDACTION_MARKER in res.output
    ws.cleanup()
