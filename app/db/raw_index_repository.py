from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
import re

from app.domain.markdown_parser import ParsedDocument


@dataclass(frozen=True)
class ReplaceDocumentsSummary:
    files_indexed: int
    raw_sections_indexed: int


@dataclass(frozen=True)
class UpsertConceptCardsSummary:
    created: int
    updated: int


@dataclass(frozen=True)
class RawSectionSearchResult:
    document_path: str
    heading: str
    heading_path: str
    chunk_index: int
    content: str
    citation: str
    token_count: int
    block_types_present: list[str]
    score: float


@dataclass(frozen=True)
class QueryRecord:
    query_text: str
    status: str
    retrieval_mode: str
    answer: str
    citations: list[str]
    used_cards: list[str]
    used_raw_sections: list[str]
    top_card_score: float | None
    top_raw_score: float | None


@dataclass(frozen=True)
class ActiveDocumentRecord:
    path: str
    content_hash: str


@dataclass(frozen=True)
class ConceptCardRecord:
    title: str
    summary: str
    key_points: list[str]
    raw_sources: list[str]


@dataclass(frozen=True)
class ConceptCardSearchResult:
    title: str
    summary: str
    key_points: list[str]
    raw_sources: list[str]
    score: float


def initialize_raw_index_schema(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_document (
                document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                title TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                raw_markdown TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_source_document_active_path
            ON source_document(path)
            WHERE is_active = 1;

            CREATE TABLE IF NOT EXISTS raw_section (
                section_id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                document_path TEXT NOT NULL,
                heading TEXT NOT NULL,
                heading_path TEXT NOT NULL,
                section_level INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                citation TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                block_types_present TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (document_id) REFERENCES source_document(document_id)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS raw_section_fts USING fts5(
                heading,
                heading_path,
                content,
                citation,
                section_id UNINDEXED
            );

            CREATE TABLE IF NOT EXISTS query_record (
                query_id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT NOT NULL,
                status TEXT NOT NULL,
                retrieval_mode TEXT NOT NULL,
                answer TEXT NOT NULL,
                citations TEXT NOT NULL,
                used_cards TEXT NOT NULL,
                used_raw_sections TEXT NOT NULL,
                top_card_score REAL,
                top_raw_score REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS concept_card (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                summary TEXT NOT NULL,
                key_points TEXT NOT NULL,
                raw_sources TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS concept_card_source (
                card_id INTEGER NOT NULL,
                section_citation TEXT NOT NULL,
                source_order INTEGER NOT NULL,
                FOREIGN KEY (card_id) REFERENCES concept_card(card_id)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS concept_card_fts USING fts5(
                title,
                summary,
                key_points,
                card_id UNINDEXED
            );
            """
        )
        _ensure_query_record_columns(connection)
        connection.commit()
    finally:
        connection.close()


class RawIndexRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def replace_documents(self, documents: list[ParsedDocument]) -> ReplaceDocumentsSummary:
        raw_sections_indexed = 0
        connection = sqlite3.connect(self._database_path)
        try:
            with connection:
                for document in documents:
                    existing_row = connection.execute(
                        "SELECT document_id FROM source_document WHERE path = ? AND is_active = 1",
                        (document.path,),
                    ).fetchone()
                    if existing_row is not None:
                        document_id = int(existing_row[0])
                        connection.execute(
                            "UPDATE source_document SET is_active = 0 WHERE document_id = ?",
                            (document_id,),
                        )
                        connection.execute(
                            "UPDATE raw_section SET is_active = 0 WHERE document_id = ?",
                            (document_id,),
                        )
                        connection.execute(
                            """
                            DELETE FROM raw_section_fts
                            WHERE section_id IN (
                                SELECT section_id FROM raw_section WHERE document_id = ?
                            )
                            """,
                            (document_id,),
                        )

                    cursor = connection.execute(
                        """
                        INSERT INTO source_document (
                            path, title, content_hash, raw_markdown, is_active
                        ) VALUES (?, ?, ?, ?, 1)
                        """,
                        (
                            document.path,
                            document.title,
                            document.content_hash,
                            document.raw_markdown,
                        ),
                    )
                    new_document_id = int(cursor.lastrowid)

                    for section in document.sections:
                        section_cursor = connection.execute(
                            """
                            INSERT INTO raw_section (
                                document_id,
                                document_path,
                                heading,
                                heading_path,
                                section_level,
                                chunk_index,
                                content,
                                citation,
                                token_count,
                                block_types_present,
                                is_active
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                            """,
                            (
                                new_document_id,
                                section.document_path,
                                section.heading,
                                section.heading_path,
                                section.level,
                                section.chunk_index,
                                section.content,
                                section.citation,
                                section.token_count,
                                json.dumps(section.block_types_present),
                            ),
                        )
                        section_id = int(section_cursor.lastrowid)
                        connection.execute(
                            """
                            INSERT INTO raw_section_fts (
                                rowid, heading, heading_path, content, citation, section_id
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                section_id,
                                section.heading,
                                section.heading_path,
                                section.content,
                                section.citation,
                                section_id,
                            ),
                        )
                        raw_sections_indexed += 1

            return ReplaceDocumentsSummary(
                files_indexed=len(documents),
                raw_sections_indexed=raw_sections_indexed,
            )
        finally:
            connection.close()

    def search_raw_sections(self, query: str, *, limit: int) -> list[RawSectionSearchResult]:
        normalized_query = _normalize_fts_query(query)
        if not normalized_query:
            return []
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT
                    rs.document_path,
                    rs.heading,
                    rs.heading_path,
                    rs.chunk_index,
                    rs.content,
                    rs.citation,
                    rs.token_count,
                    rs.block_types_present,
                    bm25(raw_section_fts) AS score
                FROM raw_section_fts fts
                JOIN raw_section rs ON rs.section_id = fts.rowid
                WHERE raw_section_fts MATCH ? AND rs.is_active = 1
                ORDER BY bm25(raw_section_fts)
                LIMIT ?
                """,
                (normalized_query, limit),
            ).fetchall()
            return [
                RawSectionSearchResult(
                    document_path=row["document_path"],
                    heading=row["heading"],
                    heading_path=row["heading_path"],
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                    citation=row["citation"],
                    token_count=row["token_count"],
                    block_types_present=json.loads(row["block_types_present"]),
                    score=float(row["score"]),
                )
                for row in rows
            ]
        finally:
            connection.close()

    def has_active_index(self) -> bool:
        if not self._database_path.exists():
            return False
        connection = sqlite3.connect(self._database_path)
        try:
            row = connection.execute(
                "SELECT 1 FROM raw_section WHERE is_active = 1 LIMIT 1"
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    def log_query_record(self, record: QueryRecord) -> None:
        if not self._database_path.exists():
            initialize_raw_index_schema(self._database_path)
        connection = sqlite3.connect(self._database_path)
        try:
            with connection:
                connection.execute(
                    """
                    INSERT INTO query_record (
                        query_text,
                        status,
                        retrieval_mode,
                        answer,
                        citations,
                        used_cards,
                        used_raw_sections,
                        top_card_score,
                        top_raw_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.query_text,
                        record.status,
                        record.retrieval_mode,
                        record.answer,
                        json.dumps(record.citations),
                        json.dumps(record.used_cards),
                        json.dumps(record.used_raw_sections),
                        record.top_card_score,
                        record.top_raw_score,
                    ),
                )
        finally:
            connection.close()

    def list_query_records(self) -> list[QueryRecord]:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT
                    query_text,
                    status,
                    retrieval_mode,
                    answer,
                    citations,
                    used_cards,
                    used_raw_sections,
                    top_card_score,
                    top_raw_score
                FROM query_record
                ORDER BY query_id ASC
                """
            ).fetchall()
            return [
                QueryRecord(
                    query_text=row["query_text"],
                    status=row["status"],
                    retrieval_mode=row["retrieval_mode"],
                    answer=row["answer"],
                    citations=json.loads(row["citations"]),
                    used_cards=json.loads(row["used_cards"]),
                    used_raw_sections=json.loads(row["used_raw_sections"]),
                    top_card_score=row["top_card_score"],
                    top_raw_score=row["top_raw_score"],
                )
                for row in rows
            ]
        finally:
            connection.close()

    def list_active_documents(self) -> list[ActiveDocumentRecord]:
        if not self._database_path.exists():
            return []
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT path, content_hash
                FROM source_document
                WHERE is_active = 1
                ORDER BY path ASC
                """
            ).fetchall()
            return [
                ActiveDocumentRecord(
                    path=row["path"],
                    content_hash=row["content_hash"],
                )
                for row in rows
            ]
        finally:
            connection.close()

    def deactivate_deleted_paths(self, paths: list[str]) -> None:
        if not paths or not self._database_path.exists():
            return
        connection = sqlite3.connect(self._database_path)
        try:
            with connection:
                for path in paths:
                    row = connection.execute(
                        """
                        SELECT document_id
                        FROM source_document
                        WHERE path = ? AND is_active = 1
                        """,
                        (path,),
                    ).fetchone()
                    if row is None:
                        continue
                    document_id = int(row[0])
                    connection.execute(
                        "UPDATE source_document SET is_active = 0 WHERE document_id = ?",
                        (document_id,),
                    )
                    connection.execute(
                        "UPDATE raw_section SET is_active = 0 WHERE document_id = ?",
                        (document_id,),
                    )
                    connection.execute(
                        """
                        DELETE FROM raw_section_fts
                        WHERE rowid IN (
                            SELECT section_id FROM raw_section WHERE document_id = ?
                        )
                        """,
                        (document_id,),
                    )
        finally:
            connection.close()

    def upsert_concept_cards(self, cards: list[ConceptCardRecord]) -> UpsertConceptCardsSummary:
        created = 0
        updated = 0
        connection = sqlite3.connect(self._database_path)
        try:
            with connection:
                for card in cards:
                    existing_row = connection.execute(
                        "SELECT card_id FROM concept_card WHERE title = ?",
                        (card.title,),
                    ).fetchone()
                    if existing_row is not None:
                        updated += 1
                        card_id = int(existing_row[0])
                        connection.execute(
                            """
                            UPDATE concept_card
                            SET summary = ?, key_points = ?, raw_sources = ?, is_active = 1
                            WHERE card_id = ?
                            """,
                            (
                                card.summary,
                                json.dumps(card.key_points),
                                json.dumps(card.raw_sources),
                                card_id,
                            ),
                        )
                        connection.execute(
                            "DELETE FROM concept_card_source WHERE card_id = ?",
                            (card_id,),
                        )
                        connection.execute(
                            "DELETE FROM concept_card_fts WHERE rowid = ?",
                            (card_id,),
                        )
                    else:
                        created += 1
                        cursor = connection.execute(
                            """
                            INSERT INTO concept_card (
                                title, summary, key_points, raw_sources, is_active
                            ) VALUES (?, ?, ?, ?, 1)
                            """,
                            (
                                card.title,
                                card.summary,
                                json.dumps(card.key_points),
                                json.dumps(card.raw_sources),
                            ),
                        )
                        card_id = int(cursor.lastrowid)

                    for index, raw_source in enumerate(card.raw_sources):
                        connection.execute(
                            """
                            INSERT INTO concept_card_source (
                                card_id, section_citation, source_order
                            ) VALUES (?, ?, ?)
                            """,
                            (card_id, raw_source, index),
                        )
                    connection.execute(
                        """
                        INSERT INTO concept_card_fts (
                            rowid, title, summary, key_points, card_id
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            card_id,
                            card.title,
                            card.summary,
                            "\n".join(card.key_points),
                            card_id,
                        ),
                    )
        finally:
            connection.close()
        return UpsertConceptCardsSummary(created=created, updated=updated)

    def replace_concept_cards(self, cards: list[ConceptCardRecord]) -> None:
        desired_titles = {card.title for card in cards}
        connection = sqlite3.connect(self._database_path)
        try:
            with connection:
                if desired_titles:
                    placeholders = ",".join("?" for _ in desired_titles)
                    connection.execute(
                        f"""
                        UPDATE concept_card
                        SET is_active = 0
                        WHERE is_active = 1 AND title NOT IN ({placeholders})
                        """,
                        tuple(sorted(desired_titles)),
                    )
                else:
                    connection.execute(
                        "UPDATE concept_card SET is_active = 0 WHERE is_active = 1"
                    )
        finally:
            connection.close()
        self.upsert_concept_cards(cards)

    def deactivate_unsupported_cards(self) -> None:
        connection = sqlite3.connect(self._database_path)
        try:
            with connection:
                connection.execute(
                    """
                    UPDATE concept_card
                    SET is_active = 0
                    WHERE is_active = 1
                      AND NOT EXISTS (
                        SELECT 1
                        FROM concept_card_source ccs
                        JOIN raw_section rs
                          ON rs.citation = ccs.section_citation AND rs.is_active = 1
                        WHERE ccs.card_id = concept_card.card_id
                      )
                    """
                )
        finally:
            connection.close()

    def search_concept_cards(self, query: str, *, limit: int) -> list[ConceptCardSearchResult]:
        normalized_query = _normalize_fts_query(query)
        if not normalized_query:
            return []
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT
                    cc.title,
                    cc.summary,
                    cc.key_points,
                    cc.raw_sources,
                    bm25(concept_card_fts) AS score
                FROM concept_card_fts fts
                JOIN concept_card cc ON cc.card_id = fts.rowid
                WHERE concept_card_fts MATCH ? AND cc.is_active = 1
                ORDER BY bm25(concept_card_fts)
                LIMIT ?
                """,
                (normalized_query, limit),
            ).fetchall()
            return [
                ConceptCardSearchResult(
                    title=row["title"],
                    summary=row["summary"],
                    key_points=json.loads(row["key_points"]),
                    raw_sources=json.loads(row["raw_sources"]),
                    score=float(row["score"]),
                )
                for row in rows
            ]
        finally:
            connection.close()

    def get_raw_sections_by_citations(
        self,
        citations: list[str],
    ) -> list[RawSectionSearchResult]:
        if not citations:
            return []
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            placeholders = ",".join("?" for _ in citations)
            rows = connection.execute(
                f"""
                SELECT
                    document_path,
                    heading,
                    heading_path,
                    chunk_index,
                    content,
                    citation,
                    token_count,
                    block_types_present
                FROM raw_section
                WHERE is_active = 1 AND citation IN ({placeholders})
                """,
                tuple(citations),
            ).fetchall()
            rows_by_citation = {
                row["citation"]: RawSectionSearchResult(
                    document_path=row["document_path"],
                    heading=row["heading"],
                    heading_path=row["heading_path"],
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                    citation=row["citation"],
                    token_count=row["token_count"],
                    block_types_present=json.loads(row["block_types_present"]),
                    score=0.0,
                )
                for row in rows
            }
            return [
                rows_by_citation[citation]
                for citation in citations
                if citation in rows_by_citation
            ]
        finally:
            connection.close()


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "are",
    "do",
    "does",
    "how",
    "i",
    "is",
    "long",
    "of",
    "take",
    "the",
    "to",
    "what",
    "which",
}


def _normalize_fts_query(query: str) -> str:
    terms = [
        term
        for term in TOKEN_PATTERN.findall(query.lower())
        if term not in STOPWORDS
    ]
    if not terms:
        return ""
    unique_terms = list(dict.fromkeys(terms))
    numeric_terms = [term for term in unique_terms if term.isdigit()]
    lexical_terms = [term for term in unique_terms if not term.isdigit()]

    clauses: list[str] = []
    if numeric_terms:
        clauses.extend(numeric_terms)
    if lexical_terms:
        lexical_clause = " OR ".join(lexical_terms)
        if len(lexical_terms) > 1:
            lexical_clause = f"({lexical_clause})"
        clauses.append(lexical_clause)
    return " AND ".join(clauses)


def _ensure_query_record_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(query_record)").fetchall()
    }
    if "top_card_score" not in existing_columns:
        connection.execute("ALTER TABLE query_record ADD COLUMN top_card_score REAL")
    if "top_raw_score" not in existing_columns:
        connection.execute("ALTER TABLE query_record ADD COLUMN top_raw_score REAL")
