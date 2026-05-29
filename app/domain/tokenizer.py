from __future__ import annotations

import re

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")

STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "are",
        "do",
        "does",
        "how",
        "i",
        "is",
        "long",
        "nearby",
        "of",
        "take",
        "the",
        "to",
        "what",
        "which",
    }
)


def tokenize(text: str) -> set[str]:
    return {term for term in TOKEN_PATTERN.findall(text.lower()) if term not in STOPWORDS}


def normalize_fts_query(query: str) -> str:
    terms = [term for term in TOKEN_PATTERN.findall(query.lower()) if term not in STOPWORDS]
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
