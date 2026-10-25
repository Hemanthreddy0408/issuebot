from types import SimpleNamespace as NS

from issuebot.llm.anthropic_client import AnthropicClient


class FakeMessages:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return NS(
            content=[
                NS(type="text", text="Plan."),
                NS(type="tool_use", id="tu_1", name="read_file", input={"path": "a.py"}),
            ],
            usage=NS(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=3,
                cache_creation_input_tokens=None,
            ),
        )


def test_parses_response_and_marks_cache():
    fake = NS(messages=FakeMessages())
    c = AnthropicClient("m", client=fake)
    r = c.complete("sys", [{"role": "user", "content": "hi"}], [])
    assert r.text == "Plan."
    assert r.tool_calls[0].name == "read_file" and r.tool_calls[0].arguments == {"path": "a.py"}
    assert (r.input_tokens, r.output_tokens, r.cache_read_tokens, r.cache_write_tokens) == (
        10,
        5,
        3,
        0,
    )
    assert fake.messages.kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
