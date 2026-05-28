from app.domain.markdown_parser import parse_markdown_document, parse_markdown_sections


def test_parse_markdown_sections_extracts_sections_from_headings() -> None:
    markdown = """# Refund Policy
Refunds are processed within 5 business days.

## Eligibility
Only unused items are eligible.
"""

    sections = parse_markdown_sections(
        document_path="docs/refund_policy.md",
        markdown=markdown,
        max_chunk_chars=1_000,
    )

    assert len(sections) == 2
    assert sections[0].heading == "Refund Policy"
    assert sections[0].heading_path == "Refund Policy"
    assert sections[0].chunk_index == 0
    assert sections[0].citation == "refund_policy.md#refund-policy"
    assert "5 business days" in sections[0].content
    assert sections[1].heading == "Eligibility"
    assert sections[1].heading_path == "Refund Policy > Eligibility"
    assert sections[1].citation == "refund_policy.md#eligibility"


def test_parse_markdown_sections_tracks_nested_heading_paths() -> None:
    markdown = """# Account Help
General guidance.

## Login Issues
Reset your password first.

### MFA
Use a backup code if the authenticator is unavailable.
"""

    sections = parse_markdown_sections(
        document_path="docs/account_help.md",
        markdown=markdown,
        max_chunk_chars=1_000,
    )

    assert [section.heading_path for section in sections] == [
        "Account Help",
        "Account Help > Login Issues",
        "Account Help > Login Issues > MFA",
    ]


def test_parse_markdown_sections_splits_long_sections_into_subchunks() -> None:
    markdown = """# Shipping FAQ
Paragraph one explains shipping windows.

Paragraph two explains expedited handling.

Paragraph three explains rural delivery delays.
"""

    sections = parse_markdown_sections(
        document_path="docs/shipping_faq.md",
        markdown=markdown,
        max_chunk_chars=70,
    )

    assert len(sections) == 3
    assert [section.chunk_index for section in sections] == [0, 1, 2]
    assert {section.citation for section in sections} == {"shipping_faq.md#shipping-faq"}
    assert all(section.heading_path == "Shipping FAQ" for section in sections)


def test_parse_markdown_sections_preserves_block_content() -> None:
    markdown = """# Change Email Address
- Go to settings
- Choose profile

```text
You may need to verify your current email.
```
"""

    sections = parse_markdown_sections(
        document_path="docs/account_help.md",
        markdown=markdown,
        max_chunk_chars=1_000,
    )

    assert len(sections) == 1
    assert "- Go to settings" in sections[0].content
    assert "verify your current email" in sections[0].content


def test_parse_markdown_sections_preserves_blank_lines_inside_fenced_code_blocks() -> None:
    markdown = """# Example
```python
def foo():
    x = 1

    return x
```
"""

    sections = parse_markdown_sections(
        document_path="docs/example.md",
        markdown=markdown,
        max_chunk_chars=1_000,
    )

    assert len(sections) == 1
    assert "def foo():" in sections[0].content
    assert "    x = 1\n\n    return x" in sections[0].content


def test_parse_markdown_sections_does_not_treat_hashes_inside_fenced_code_as_headings() -> None:
    markdown = """# Example
```python
# This is a Python comment
x = 1
```
"""

    sections = parse_markdown_sections(
        document_path="docs/example.md",
        markdown=markdown,
        max_chunk_chars=1_000,
    )

    assert len(sections) == 1
    assert sections[0].heading == "Example"
    assert "# This is a Python comment" in sections[0].content


def test_parse_markdown_document_returns_document_metadata() -> None:
    markdown = """# Refund Policy
Refunds are processed within 5 business days.
"""

    document = parse_markdown_document(
        document_path="docs/refund_policy.md",
        markdown=markdown,
        max_chunk_chars=1_000,
    )

    assert document.path == "docs/refund_policy.md"
    assert document.title == "Refund Policy"
    assert document.raw_markdown == markdown
    assert len(document.content_hash) == 64
    assert document.sections[0].citation == "refund_policy.md#refund-policy"


def test_parse_markdown_document_tracks_token_count_and_block_types() -> None:
    markdown = """# Change Email Address
- Go to settings
- Choose profile

Paragraph with more details.

```text
You may need to verify your current email.
```
"""

    document = parse_markdown_document(
        document_path="docs/account_help.md",
        markdown=markdown,
        max_chunk_chars=1_000,
    )

    section = document.sections[0]

    assert section.token_count == 18
    assert section.block_types_present == ["code", "list", "paragraph"]
