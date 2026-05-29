from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

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
                (query, limit),
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
