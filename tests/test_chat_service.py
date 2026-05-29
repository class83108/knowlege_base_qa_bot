from pathlib import Path

from app.db.raw_index_repository import QueryRecord, RawSectionSearchResult
from app.services.chat import ChatService


class FakeRepository:
    def __init__(self, *, indexed: bool, results: list[RawSectionSearchResult]) -> None:
        self._indexed = indexed
        self._results = results
        self.logged: list[QueryRecord] = []

    def has_active_index(self) -> bool:
        return self._indexed

    def search_raw_sections(self, query: str, *, limit: int) -> list[RawSectionSearchResult]:
        return self._results

    def log_query_record(self, record: QueryRecord) -> None:
        self.logged.append(record)


class FakeGenerator:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


def test_chat_service_uses_generator_for_grounded_answer() -> None:
    repository = FakeRepository(
        indexed=True,
        results=[
            RawSectionSearchResult(
                document_path="docs/refund_policy.md",
                heading="Refund Timeline",
                heading_path="Refund Policy > Refund Timeline",
                chunk_index=0,
                content="Refunds are processed within 5 business days.",
                citation="refund_policy.md#refund-timeline",
                token_count=7,
                block_types_present=["paragraph"],
            )
        ],
    )
    generator = FakeGenerator(
        '{"status":"ok","answer":"Refunds take 5 business days.","citations":["refund_policy.md#refund-timeline"]}'
    )
    service = ChatService(
        database_path=Path("/tmp/not-used.db"),
        repository=repository,
        answer_generator=generator,
    )

    response = service.answer("How long do refunds take?")

    assert response["status"] == "ok"
    assert response["answer"] == "Refunds take 5 business days."
    assert response["citations"] == ["refund_policy.md#refund-timeline"]
    assert len(generator.prompts) == 1
    assert "How long do refunds take?" in generator.prompts[0]
    assert "refund_policy.md#refund-timeline" in generator.prompts[0]


def test_chat_service_can_use_generator_fallback_answer() -> None:
    repository = FakeRepository(
        indexed=True,
        results=[
            RawSectionSearchResult(
                document_path="docs/refund_policy.md",
                heading="Refund Timeline",
                heading_path="Refund Policy > Refund Timeline",
                chunk_index=0,
                content="Refunds are processed within 5 business days.",
                citation="refund_policy.md#refund-timeline",
                token_count=7,
                block_types_present=["paragraph"],
            )
        ],
    )
    generator = FakeGenerator(
        '{"status":"cannot_confirm","answer":"I cannot confirm the answer from the knowledge base.","citations":[]}'
    )
    service = ChatService(
        database_path=Path("/tmp/not-used.db"),
        repository=repository,
        answer_generator=generator,
    )

    response = service.answer("How long do refunds take?")

    assert response["status"] == "cannot_confirm"
    assert response["answer"] == "I cannot confirm the answer from the knowledge base."
