from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol


class AnswerGenerator(Protocol):
    def generate(self, prompt: str) -> "AnswerGenerationResult": ...


@dataclass(frozen=True)
class GroundedAnswerResponse:
    status: str
    answer: str
    citations: list[str]


@dataclass(frozen=True)
class AnswerGenerationResult:
    payload: str
    input_tokens: int | None = None
    output_tokens: int | None = None


_CANNOT_CONFIRM_JSON = json.dumps(
    {
        "status": "cannot_confirm",
        "answer": "I cannot confirm the answer from the knowledge base.",
        "citations": [],
    }
)


class EchoEvidenceGenerator:
    def generate(self, prompt: str) -> AnswerGenerationResult:
        marker = "Evidence:\n"
        if marker not in prompt:
            return AnswerGenerationResult(payload=_CANNOT_CONFIRM_JSON)
        evidence = prompt.split(marker, maxsplit=1)[1].strip()
        citations = []
        for block in evidence.split("\n\n"):
            if block.startswith("[") and "]" in block:
                citations.append(block[1 : block.index("]")])
        answer_text = "\n\n".join(
            line
            for block in evidence.split("\n\n")
            for line in block.splitlines()[1:]
        ).strip()
        return AnswerGenerationResult(
            payload=json.dumps(
                {
                    "status": "ok",
                    "answer": answer_text,
                    "citations": citations,
                }
            )
        )


class OpenAIResponsesGenerator:
    def __init__(self, *, model: str, client=None, api_key: str | None = None) -> None:
        self._model = model
        if client is not None:
            self._client = client
            return

        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)

    def generate(self, prompt: str) -> AnswerGenerationResult:
        try:
            response = self._client.responses.create(
                model=self._model,
                input=prompt,
                text={"format": GROUNDED_ANSWER_FORMAT},
            )
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", None) if usage is not None else None
            output_tokens = getattr(usage, "output_tokens", None) if usage is not None else None
            return AnswerGenerationResult(
                payload=response.output_text or _CANNOT_CONFIRM_JSON,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            return AnswerGenerationResult(payload=_CANNOT_CONFIRM_JSON)


def build_answer_generator(
    *,
    openai_api_key: str | None,
    openai_model: str,
) -> AnswerGenerator:
    if not openai_api_key:
        return EchoEvidenceGenerator()
    return OpenAIResponsesGenerator(
        model=openai_model,
        api_key=openai_api_key,
    )


def parse_grounded_answer_response(payload: str) -> GroundedAnswerResponse:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("Response payload is not valid JSON") from exc

    status = data.get("status")
    if status not in {"ok", "cannot_confirm"}:
        raise ValueError("Response payload has invalid status")

    answer = data.get("answer")
    citations = data.get("citations")
    if not isinstance(answer, str):
        raise ValueError("Response payload has invalid answer")
    if not isinstance(citations, list) or not all(
        isinstance(item, str) for item in citations
    ):
        raise ValueError("Response payload has invalid citations")

    return GroundedAnswerResponse(
        status=status,
        answer=answer,
        citations=citations,
    )


GROUNDED_ANSWER_FORMAT = {
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
