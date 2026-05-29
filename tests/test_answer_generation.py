import json

from app.services.answer_generation import OpenAIResponsesGenerator, build_answer_generator


class FakeResponsesAPI:
    def __init__(
        self,
        output_text: str | None,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        self.output_text = output_text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        class Response:
            pass

        response = Response()
        response.output_text = self.output_text
        if self.input_tokens is not None or self.output_tokens is not None:
            class Usage:
                pass
            usage = Usage()
            usage.input_tokens = self.input_tokens
            usage.output_tokens = self.output_tokens
            response.usage = usage
        return response


class FailingResponsesAPI:
    def create(self, **kwargs):
        raise RuntimeError("simulated API failure")


class FakeClient:
    def __init__(
        self,
        output_text: str | None,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        self.responses = FakeResponsesAPI(
            output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class FailingClient:
    responses = FailingResponsesAPI()


def test_openai_responses_generator_uses_responses_api() -> None:
    client = FakeClient("Grounded answer.")
    generator = OpenAIResponsesGenerator(
        model="gpt-5",
        client=client,
    )

    output = generator.generate("Prompt text")

    assert output.payload == "Grounded answer."
    assert client.responses.calls == [
        {
            "model": "gpt-5",
            "input": "Prompt text",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "grounded_answer",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": "string",
                                "enum": ["ok", "cannot_confirm"],
                            },
                            "answer": {"type": "string"},
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["status", "answer", "citations"],
                        "additionalProperties": False,
                    },
                }
            },
        }
    ]


def test_generate_returns_valid_json_when_output_text_is_none() -> None:
    client = FakeClient(None)
    generator = OpenAIResponsesGenerator(model="gpt-5", client=client)

    output = generator.generate("Prompt text")

    data = json.loads(output.payload)
    assert data["status"] == "cannot_confirm"


def test_generate_returns_valid_json_when_output_text_is_empty() -> None:
    client = FakeClient("")
    generator = OpenAIResponsesGenerator(model="gpt-5", client=client)

    output = generator.generate("Prompt text")

    data = json.loads(output.payload)
    assert data["status"] == "cannot_confirm"


def test_generate_returns_cannot_confirm_on_api_exception() -> None:
    generator = OpenAIResponsesGenerator(model="gpt-5", client=FailingClient())

    output = generator.generate("Prompt text")

    data = json.loads(output.payload)
    assert data["status"] == "cannot_confirm"


def test_build_answer_generator_returns_echo_without_api_key() -> None:
    generator = build_answer_generator(
        openai_api_key=None,
        openai_model="gpt-5",
    )

    output = generator.generate("Evidence:\n[refund_policy.md#refund-timeline]\nhello")

    assert output.payload == (
        '{"status": "ok", "answer": "hello", "citations": ["refund_policy.md#refund-timeline"]}'
    )


def test_openai_responses_generator_reads_usage_tokens() -> None:
    client = FakeClient(
        '{"status":"ok","answer":"x","citations":[]}',
        input_tokens=123,
        output_tokens=45,
    )
    generator = OpenAIResponsesGenerator(model="gpt-5", client=client)

    output = generator.generate("Prompt text")

    assert output.input_tokens == 123
    assert output.output_tokens == 45
