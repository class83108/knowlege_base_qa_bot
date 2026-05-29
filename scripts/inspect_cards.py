"""Inspect concept cards alongside their source raw sections."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(".kb/knowledge_base.db")


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Run POST /index first.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cards = conn.execute("""
        SELECT cc.card_id, cc.title, cc.summary, cc.key_points, cc.related_cards,
               GROUP_CONCAT(ccs.section_citation, '|') AS citations
        FROM concept_card cc
        JOIN concept_card_source ccs ON ccs.card_id = cc.card_id
        WHERE cc.is_active = 1
        GROUP BY cc.card_id
        ORDER BY cc.card_id
    """).fetchall()

    all_card_titles = {
        row["title"]
        for row in conn.execute("SELECT title FROM concept_card WHERE is_active = 1")
    }

    print(f"Active cards: {len(cards)}\n")

    for card in cards:
        citations = card["citations"].split("|") if card["citations"] else []
        sections = conn.execute(
            f"SELECT citation, content FROM raw_section"
            f" WHERE citation IN ({','.join('?' for _ in citations)}) AND is_active = 1",
            citations,
        ).fetchall()
        source_by_citation = {s["citation"]: s["content"] for s in sections}

        key_points: list[str] = json.loads(card["key_points"])
        related_cards: list[str] = json.loads(card["related_cards"])
        missing_related = [r for r in related_cards if r not in all_card_titles]

        print(f"{'=' * 60}")
        print(f"[{card['card_id']}] {card['title']}")
        print(f"{'=' * 60}")
        print(f"SUMMARY:\n  {card['summary']}\n")
        print("KEY POINTS:")
        for kp in key_points:
            print(f"  - {kp}")
        print()
        if related_cards:
            print("RELATED CARDS:")
            for r in related_cards:
                marker = " ⚠ (not found)" if r in missing_related else ""
                print(f"  - {r}{marker}")
            print()
        print("SOURCE SECTIONS:")
        for citation in citations:
            content = source_by_citation.get(citation, "(section not found)")
            print(f"  [{citation}]")
            print(f"  {content}")
            print()

    conn.close()


if __name__ == "__main__":
    main()
