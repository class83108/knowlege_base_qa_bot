from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedDocument:
    path: str
    title: str
    content_hash: str
    raw_markdown: str
    sections: list["ParsedSection"]


@dataclass(frozen=True)
class ParsedSection:
    document_path: str
    heading: str
    heading_path: str
    level: int
    chunk_index: int
    content: str
    citation: str
    token_count: int
    block_types_present: list[str]


@dataclass(frozen=True)
class _SectionBlock:
    content: str
    block_type: str


@dataclass
class _SectionBuffer:
    heading: str
    heading_path: str
    level: int
    blocks: list[_SectionBlock]


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FENCE_PATTERN = re.compile(r"^(```+|~~~+)")
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
WORD_PATTERN = re.compile(r"[A-Za-z0-9]+")
LIST_LINE_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+\.\s+)")


def parse_markdown_document(
    document_path: str,
    markdown: str,
    *,
    max_chunk_chars: int,
) -> ParsedDocument:
    sections = parse_markdown_sections(
        document_path=document_path,
        markdown=markdown,
        max_chunk_chars=max_chunk_chars,
    )
    title = sections[0].heading if sections else Path(document_path).stem
    return ParsedDocument(
        path=document_path,
        title=title,
        content_hash=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        raw_markdown=markdown,
        sections=sections,
    )


def parse_markdown_sections(
    document_path: str,
    markdown: str,
    *,
    max_chunk_chars: int,
) -> list[ParsedSection]:
    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars must be positive")

    lines = markdown.splitlines()
    sections: list[_SectionBuffer] = []
    heading_stack: list[tuple[int, str]] = []
    current: _SectionBuffer | None = None
    block_lines: list[str] = []
    active_fence: str | None = None

    def flush_block() -> None:
        nonlocal block_lines, current
        if current is None:
            block_lines = []
            return
        text = "\n".join(block_lines).strip()
        if text:
            current.blocks.append(
                _SectionBlock(
                    content=text,
                    block_type=_classify_block(text),
                )
            )
        block_lines = []

    def start_section(level: int, heading: str) -> _SectionBuffer:
        nonlocal current, heading_stack
        flush_block()
        heading_stack = [item for item in heading_stack if item[0] < level]
        heading_stack.append((level, heading))
        current = _SectionBuffer(
            heading=heading,
            heading_path=" > ".join(title for _, title in heading_stack),
            level=level,
            blocks=[],
        )
        sections.append(current)
        return current

    for line in lines:
        fence_match = FENCE_PATTERN.match(line)
        if active_fence is not None:
            if current is not None:
                block_lines.append(line.rstrip())
            if fence_match and fence_match.group(1).startswith(active_fence[0]):
                active_fence = None
            continue

        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            heading = heading_match.group(2).strip()
            start_section(level, heading)
            continue

        if current is None:
            continue

        if fence_match:
            block_lines.append(line.rstrip())
            active_fence = fence_match.group(1)
            continue

        if line.strip():
            block_lines.append(line.rstrip())
        else:
            flush_block()

    flush_block()

    if not sections and markdown.strip():
        fallback_heading = Path(document_path).stem
        current = _SectionBuffer(
            heading=fallback_heading,
            heading_path=fallback_heading,
            level=1,
            blocks=[
                _SectionBlock(
                    content=markdown.strip(),
                    block_type=_classify_block(markdown.strip()),
                )
            ],
        )
        sections.append(current)

    parsed_sections: list[ParsedSection] = []
    for section in sections:
        parsed_sections.extend(
            _chunk_section(
                document_path=document_path,
                section=section,
                max_chunk_chars=max_chunk_chars,
            )
        )
    return parsed_sections


def _chunk_section(
    *,
    document_path: str,
    section: _SectionBuffer,
    max_chunk_chars: int,
) -> list[ParsedSection]:
    chunks: list[tuple[str, list[str]]] = []
    current_chunk = ""
    current_block_types: list[str] = []

    for block in section.blocks:
        candidate = (
            block.content
            if not current_chunk
            else f"{current_chunk}\n\n{block.content}"
        )
        if current_chunk and len(candidate) > max_chunk_chars:
            chunks.append((current_chunk, sorted(set(current_block_types))))
            current_chunk = block.content
            current_block_types = [block.block_type]
            continue
        current_chunk = candidate
        current_block_types.append(block.block_type)

    if current_chunk:
        chunks.append((current_chunk, sorted(set(current_block_types))))

    if not chunks:
        chunks = [("", [])]

    citation = _build_citation(document_path=document_path, heading=section.heading)
    return [
        ParsedSection(
            document_path=document_path,
            heading=section.heading,
            heading_path=section.heading_path,
            level=section.level,
            chunk_index=index,
            content=content,
            citation=citation,
            token_count=_count_tokens(content),
            block_types_present=block_types_present,
        )
        for index, (content, block_types_present) in enumerate(chunks)
    ]


def _build_citation(*, document_path: str, heading: str) -> str:
    filename = Path(document_path).name
    slug = NON_ALNUM_PATTERN.sub("-", heading.lower()).strip("-")
    return f"{filename}#{slug}"


def _count_tokens(content: str) -> int:
    return len(WORD_PATTERN.findall(content))


def _classify_block(text: str) -> str:
    lines = text.splitlines()
    if lines and FENCE_PATTERN.match(lines[0]):
        return "code"
    if lines and all(LIST_LINE_PATTERN.match(line) for line in lines):
        return "list"
    return "paragraph"
