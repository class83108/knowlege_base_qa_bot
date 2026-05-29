from app.services.answer_generation import OpenAIResponsesGenerator, build_answer_generator


class FakeResponsesAPI:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        class Response:
            pass

        response = Response()
        response.output_text = self.output_text
        return response


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponsesAPI(output_text)


def test_openai_responses_generator_uses_responses_api() -> None:
    client = FakeClient("Grounded answer.")
    generator = OpenAIResponsesGenerator(
        model="gpt-5",
        client=client,
    )

    output = generator.generate("Prompt text")

    assert output == "Grounded answer."
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


def test_build_answer_generator_returns_echo_without_api_key() -> None:
    generator = build_answer_generator(
        openai_api_key=None,
        openai_model="gpt-5",
    )

    output = generator.generate("Evidence:\n[refund_policy.md#refund-timeline]\nhello")

    assert output == (
        '{"status": "ok", "answer": "hello", "citations": ["refund_policy.md#refund-timeline"]}'
    )
