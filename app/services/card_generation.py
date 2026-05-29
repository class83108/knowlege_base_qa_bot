from __future__ import annotations

import json

from app.domain.concept_card_builder import CardGenerator, GeneratedCardContent


CARD_CONTENT_FORMAT = {
    "type": "json_schema",
    "name": "card_content",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["summary", "key_points"],
        "additionalProperties": False,
    },
}


def _build_card_prompt(title: str, sections: list[str]) -> str:
    sections_text = "\n\n---\n\n".join(sections)
    return (
        f"You are maintaining a knowledge base. "
        f"Generate a concise concept card for the topic below.\n\n"
        f"Topic: {title}\n\n"
        f"Source content:\n{sections_text}\n\n"
        f"Write a 2-3 sentence summary and extract 3-5 key points."
    )


def _fallback_content(sections: list[str]) -> GeneratedCardContent:
    return GeneratedCardContent(
        summary="\n\n".join(sections),
        key_points=list(sections),
    )


def _parse_card_response(payload: str, sections: list[str]) -> GeneratedCardContent:
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, Exception):
        return _fallback_content(sections)
    summary = data.get("summary")
    key_points = data.get("key_points")
    if not isinstance(summary, str):
        return _fallback_content(sections)
    if not isinstance(key_points, list) or not all(isinstance(p, str) for p in key_points):
        return _fallback_content(sections)
    return GeneratedCardContent(summary=summary, key_points=key_points)


class OpenAICardGenerator:
    def __init__(self, *, model: str, client=None, api_key: str | None = None) -> None:
        self._model = model
        if client is not None:
            self._client = client
            return
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)

    def generate(self, title: str, sections: list[str]) -> GeneratedCardContent:
        try:
            response = self._client.responses.create(
                model=self._model,
                input=_build_card_prompt(title, sections),
                text={"format": CARD_CONTENT_FORMAT},
            )
            return _parse_card_response(response.output_text or "", sections)
        except Exception:
            return _fallback_content(sections)


def build_card_generator(
    *,
    openai_api_key: str | None,
    openai_model: str,
) -> CardGenerator | None:
    if not openai_api_key:
        return None
    return OpenAICardGenerator(model=openai_model, api_key=openai_api_key)
