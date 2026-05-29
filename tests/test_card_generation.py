import json

from app.domain.concept_card_builder import GeneratedCardContent
from app.services.card_generation import OpenAICardGenerator, build_card_generator


class FakeCardResponsesAPI:
    def __init__(self, output_text: str | None) -> None:
        self.output_text = output_text
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        class Response:
            pass

        response = Response()
        response.output_text = self.output_text
        return response


class FailingCardResponsesAPI:
    def create(self, **kwargs):
        raise RuntimeError("simulated API failure")


class FakeCardClient:
    def __init__(self, output_text: str | None) -> None:
        self.responses = FakeCardResponsesAPI(output_text)


class FailingCardClient:
    responses = FailingCardResponsesAPI()


def test_openai_card_generator_calls_responses_api() -> None:
    output = json.dumps({"summary": "LLM summary", "key_points": ["p1", "p2"]})
    client = FakeCardClient(output)
    generator = OpenAICardGenerator(model="gpt-5", client=client)

    generator.generate(title="Refund Policy", sections=["Refunds take 5 days."])

    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]
    assert call["model"] == "gpt-5"
    assert "Refund Policy" in call["input"]
    assert "Refunds take 5 days." in call["input"]
    assert call["text"]["format"]["type"] == "json_schema"


def test_openai_card_generator_returns_parsed_content() -> None:
    output = json.dumps({"summary": "LLM summary", "key_points": ["p1", "p2"]})
    client = FakeCardClient(output)
    generator = OpenAICardGenerator(model="gpt-5", client=client)

    result = generator.generate(title="Refund Policy", sections=["Refunds take 5 days."])

    assert result.summary == "LLM summary"
    assert result.key_points == ["p1", "p2"]


def test_openai_card_generator_falls_back_on_none_output() -> None:
    client = FakeCardClient(None)
    generator = OpenAICardGenerator(model="gpt-5", client=client)

    result = generator.generate(title="Refund Policy", sections=["Refunds take 5 days."])

    assert isinstance(result, GeneratedCardContent)
    assert "Refunds take 5 days." in result.summary


def test_openai_card_generator_falls_back_on_api_exception() -> None:
    generator = OpenAICardGenerator(model="gpt-5", client=FailingCardClient())

    result = generator.generate(title="Refund Policy", sections=["Refunds take 5 days."])

    assert isinstance(result, GeneratedCardContent)
    assert "Refunds take 5 days." in result.summary


def test_openai_card_generator_parses_related_cards() -> None:
    output = json.dumps({
        "summary": "LLM summary",
        "key_points": ["p1"],
        "related_cards": ["Shipping Policy", "Returns FAQ"],
    })
    client = FakeCardClient(output)
    generator = OpenAICardGenerator(model="gpt-5", client=client)

    result = generator.generate(title="Refund Policy", sections=["Refunds take 5 days."])

    assert result.related_cards == ["Shipping Policy", "Returns FAQ"]


def test_openai_card_generator_defaults_related_cards_to_empty_when_missing() -> None:
    output = json.dumps({"summary": "LLM summary", "key_points": ["p1"]})
    client = FakeCardClient(output)
    generator = OpenAICardGenerator(model="gpt-5", client=client)

    result = generator.generate(title="Refund Policy", sections=["Refunds take 5 days."])

    assert result.related_cards == []


def test_build_card_generator_returns_none_without_api_key() -> None:
    assert build_card_generator(openai_api_key=None, openai_model="gpt-5") is None


def test_build_card_generator_returns_openai_generator_with_api_key() -> None:
    generator = build_card_generator(openai_api_key="sk-test", openai_model="gpt-5")
    assert isinstance(generator, OpenAICardGenerator)
