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
class RawSectionSearchResult:
    document_path: str
    heading: str
    heading_path: str
    chunk_index: int
    content: str
    citation: str
    token_count: int
    block_types_present: list[str]


@dataclass(frozen=True)
class QueryRecord:
    query_text: str
    status: str
    retrieval_mode: str
    answer: str
    citations: list[str]
    used_cards: list[str]
    used_raw_sections: list[str]


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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
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
                    rs.block_types_present
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
                        used_raw_sections
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.query_text,
                        record.status,
                        record.retrieval_mode,
                        record.answer,
                        json.dumps(record.citations),
                        json.dumps(record.used_cards),
                        json.dumps(record.used_raw_sections),
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
                    used_raw_sections
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
                )
                for row in rows
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
    return " AND ".join(dict.fromkeys(terms))
