# Knowledge Base Q&A Bot

This is a knowledge base Q&A service built along the `Markdown KB` path, with an additional `concept card` layer on top of raw Markdown sections.

The project is intentionally narrow in scope. It is not a general-purpose RAG platform, and it is not an agent system. It is a bounded-domain, inspectable, traceable, grounded Q&A service focused on single-turn question answering. The goal is not only to "produce an answer," but to make retrieval, evidence selection, citation, and fallback behavior explicit and debuggable.

## Project Goal

The goal of this project is to turn local `docs/*.md` files into a grounded Q&A service that:

- breaks Markdown into inspectable retrieval units
- maintains a concept-card layer as a progressive disclosure knowledge layer
- answers only from retrieved evidence
- cites sources using `filename#heading`
- returns `cannot_confirm` when support is insufficient

This direction comes from the `Markdown KB` path described in [`PROMPT.md`](/Users/nb050/knowlege_base_qa_bot/PROMPT.md), and is also influenced by Andrej Karpathy's `LLM Wiki` idea: using Markdown as the knowledge substrate, explicit indexes for inspectability, and an LLM-readable compiled knowledge layer. This repo is not trying to become a fully autonomous wiki product. It applies that idea in a narrower, verifiable QA setting. See Karpathy's original gist: [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Our Mindset

- Grounded correctness matters more than answer completeness.
- The system should be able to say `cannot_confirm` honestly.
- Retrieval behavior should be inspectable, not a black box.
- Raw Markdown remains the source of truth.
- The spirit of concept cards is that the LLM first organizes raw knowledge into higher-level, readable content, so queries can start from cards instead of always searching every raw section directly.
- Concept cards support retrieval and progressive disclosure, but they do not replace raw evidence. Cards are query entry points; raw sections provide final support.
- Indexing and querying share the same knowledge segmentation and retrieval logic, so the index stage and the query stage operate on the same knowledge model.
- The value of an inverted index is not only interpretability, but also keeping multi-document retrieval fast and scalable.

## Design Questions And Our Answers

This project is built around the design questions raised in [`PROMPT.md`](/Users/nb050/knowlege_base_qa_bot/PROMPT.md).

### 1. Why choose Markdown KB instead of Vector RAG?

Because the current corpus is:

- small to medium in size
- local and controllable
- Markdown-native
- relatively bounded in domain

In that shape of problem, Markdown KB gives us:

- explicit and inspectable retrieval units
- source citations that map naturally back to the original documents
- easier debugging for weak retrieval and false positives
- a cleaner path toward a wiki-like compiled knowledge layer

This is not a claim that embeddings are bad. It is a choice to use the simpler and more interpretable retrieval approach for the current problem shape.

### 2. Why add concept cards on top of Markdown KB?

This is the main additional step beyond a plain Markdown KB.

The reason for concept cards is to create a progressive disclosure knowledge layer:

- the LLM can first look at concise concept-level summaries
- if a card looks relevant, the system can pull supporting raw sections
- if the card support is weak, the system falls back to raw retrieval

The intended flow is:

```text
query
  -> concept card retrieval
  -> raw support validation
  -> answer from grounded evidence
  -> return cannot_confirm when support is insufficient
```

This is a `wiki-first, raw-fallback` path.

Cards are not the final authority. They are the query entry point. Raw sections remain the authoritative evidence layer.

### 3. How are raw sections stored? How is chunking done, and why?

Our main retrieval unit is the `raw section`, derived from Markdown heading structure.

The reasoning is:

- `file` is too coarse
- pure `small chunk` segmentation loses Markdown structure too quickly
- `section` preserves semantic boundaries, headings, and inspectable citations

The ingestion flow is roughly:

- scan `docs/*.md`
- split content into raw sections based on Markdown heading structure
- subchunk overly long sections so prompt context stays bounded
- preserve heading, heading path, chunk index, citation, and other lineage metadata
- write both raw sections and concept cards into inspectable indexes and storage

This approach preserves human-readable Markdown structure while still keeping query cost bounded.

### 4. What determines the structure of a concept card?

A card is not just an arbitrary summary. Its structure is designed around being a usable query entry point.

At the moment, a card mainly contains:

- `title`
- `summary`
- `key points`
- `related cards`
- `raw sources`

This structure serves several purposes:

- `title / summary / key points` provide higher-level concept descriptions so a query can align with concepts before dropping to raw evidence
- `raw sources` ensure every card can be traced back to the raw evidence it currently depends on
- `related cards` preserve room for concept-level navigation and future expansion

So cards are not generated just to be readable. They are generated to support a wiki-first, raw-fallback retrieval and answering flow.

### 5. Why use an inverted index and BM25-style retrieval?

Because once document volume starts growing, Markdown KB still needs serious retrieval infrastructure.

This repo currently uses SQLite FTS-backed inverted indexes for:

- raw sections
- concept cards

That gives us inspectable lexical retrieval with:

- ranking behavior that is easier to understand and debug than embedding retrieval
- BM25-style search behavior
- lower operational complexity for a local Markdown-first system
- a practical scaling path before jumping to a vector stack

So if the question is "what happens when the number of files grows a lot?", our current answer is:

do not immediately switch everything to vector retrieval. First use well-formed retrieval units plus an inverted index, and push the Markdown KB path until it reaches a real limit.

### 6. What context goes into the prompt? How do we reduce prompt injection risk?

We deliberately constrain prompt context.

- for card-led answers, the prompt includes only raw sections that actually support the matched card
- for raw fallback answers, the prompt includes selected raw evidence, and may optionally include supporting cards
- context is bounded so `/chat` does not degrade into "dump a large amount of text into the prompt and hope"

This is also the current baseline approach for reducing prompt injection risk:

- we do not dump entire documents into the prompt unchanged
- we include only retrieved and selected evidence
- we constrain the model with a fixed grounded-answer prompt and structured output requirements
- citations must map back to actual selected raw sections

This does not make the system fully injection-proof, but it does keep the risk bounded by the retrieval scope and the response contract instead of allowing arbitrary document text to drive the whole model behavior.

### 7. How do we make sure responses have sources?

Answers cite sources in the form `filename#heading`.

That format is useful because it is:

- human-readable
- naturally aligned with Markdown structure
- easy to trace back to the original source

On top of that, the system uses constrained response structure and post-processing so the model cannot freely cite sources that were never retrieved. The answer is not judged only by semantic plausibility; it must map back to evidence.

### 8. When would we switch to Vector RAG?

Not every larger corpus should immediately trigger a switch.

If the project emphasizes domain expertise, precision, and traceability, it can still make sense to first try:

- using an LLM to normalize the query
- query rewrite or query expansion
- improving card-first retrieval quality
- tuning lexical ranking, `top-k`, and thresholds

In other words, it is reasonable to push query normalization and retrieval quality within the Markdown KB path before deciding that Vector RAG is necessary.

Vector RAG becomes more compelling when:

- synonym-heavy reformulations are common
- concepts are expressed in highly distributed ways
- lexical retrieval recall is clearly the bottleneck
- the corpus is large enough that a purely lexical card/raw path can no longer maintain enough coverage

### 9. What should happen when retrieval results are weak?

We do not force an answer.

If retrieval is weak, irrelevant, or insufficiently supported, the system returns `cannot_confirm`. That is not an edge case. It is a core project behavior.

## What This Project Intentionally Does Not Build

This problem setting is deliberately constrained.

- No tool calling, because this is not an agent workflow.
- No gateway or orchestration layer, because there is only one service boundary right now.
- No conversation memory, because the project is intentionally focused on simple QA.
- No embedding-first or vector database architecture, because the focus is Markdown KB, concept cards, inverted indexes, and BM25-style retrieval.
- No autonomous wiki that replaces raw sources, because raw docs remain the authoritative evidence.
- No large, heterogeneous, multi-domain knowledge lake, because the target is a bounded-domain, inspectable QA system.

These are deliberate tradeoffs, not missing checkboxes.

## System Overview

```text
docs/*.md
  -> Markdown ingest
  -> raw sections
  -> inverted index + manifest persistence
  -> concept card generation / maintenance
  -> /chat retrieval
       -> cards first
       -> raw support validation
       -> raw fallback when needed
       -> grounded answer with citations
```

Current API:

- `GET /health`
- `POST /index`
- `POST /chat`
- `GET /query-records`

Current persisted state:

- `.kb/index.json`: manifest for the currently indexed document set
- `.kb/knowledge_base.db`: SQLite database containing raw sections, concept cards, FTS indexes, and query logs

## How To Run Locally

### 1. Clone the project

```bash
git clone <your-repo-url>
cd knowlege_base_qa_bot
```

### 2. Install dependencies

This project uses `uv`.

```bash
uv sync
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Set at least:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
```

Notes:

- `OPENAI_API_KEY` is recommended so card generation and answer generation use the real LLM path.
- If `OPENAI_API_KEY` is not set, the system can still run, but it falls back to a local generator. That is useful for validating the flow, not for validating realistic answer quality.

### 4. Start the server

```bash
uv run uvicorn app.main:app --reload
```

Default location:

- `http://localhost:8000`

### 5. Verify the service is running

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

### 6. You must call `/index` first

This is a required prerequisite.

In the current design, `/chat` is not usable until the knowledge base has been indexed at least once.

```bash
curl -X POST http://localhost:8000/index
```

Example response:

```json
{
  "status": "ok",
  "files_indexed": 6,
  "raw_sections_indexed": 12,
  "concept_cards_created": 6,
  "concept_cards_updated": 0,
  "unchanged_documents": 0,
  "deleted_documents": 0,
  "message": "Index rebuilt successfully."
}
```

### 7. Then call `/chat`

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "How long do refunds take?"}'
```

If the evidence is sufficient, the response includes:

- `status`
- `retrieval_mode`
- `answer`
- `citations`
- `used_cards`
- `used_raw_sections`

### 8. Inspect query decisions

You can inspect query decisions through:

```bash
curl http://localhost:8000/query-records
```

This lets you inspect:

- which candidate cards were considered
- which raw sections were considered
- why the system answered or returned `cannot_confirm`
- token and latency information when available

## Correct Usage Flow

The correct order is:

```text
git clone
  -> uv sync
  -> configure .env
  -> start server
  -> POST /index
  -> POST /chat
```

If you skip `POST /index`, `POST /chat` returns `status = not_indexed`.

Whenever `docs/*.md` changes, you should run `POST /index` again.

## How We Validate Behavior

This project does not use "the answer sounds plausible" as its success criterion.

The current test coverage includes:

- calling chat before indexing returns `not_indexed`
- grounded answers include expected citations
- weak retrieval returns `cannot_confirm`
- indexing updates cards correctly when source docs change
- query records preserve retrieval and decision details

Run tests with:

```bash
uv run pytest
```

## Current Weaknesses

The main weaknesses right now are not about whether the API works. They are about evaluation and tuning.

- The current `docs/` content is not very cross-domain, so retrieval stress is limited.
- The tokenizer is still weak, especially for morphology, synonym handling, and query normalization.
- We do not yet have a strong evaluation mechanism for concept-card generation quality.
- Card quality is still validated mostly indirectly through downstream behavior rather than through dedicated card-quality evaluation.
- Lexical retrieval is inspectable, but it still has limits for synonym-heavy or heavily paraphrased queries.
- There is no dedicated upload or ingestion filtering mechanism yet; the current behavior is effectively "scan all `docs/*.md`".
- The current `top-k` choices are still somewhat hand-tuned and need more systematic calibration.
- Score thresholds also need further calibration to avoid becoming too conservative or too permissive.

In short, the key uncertainties are not "can it answer?" but:

- how much the card layer is actually helping
- whether `top-k` and threshold choices are stable across query types
- whether the card-first flow will degrade as the corpus becomes broader and noisier

## Where Iteration Should Start

If this project continues, the best next steps are:

1. Build a more complete evaluation set, especially for concept-card quality and retrieval quality.
2. Add more paraphrased, cross-domain, and easy-to-misretrieve queries to stress the card-first flow.
3. Systematically tune `top-k` and score thresholds instead of relying on fixed values.
4. Strengthen card maintenance rules: when to update, split, merge, or deactivate cards.
5. Understand the failure modes of the Markdown KB path clearly before deciding whether Vector RAG is actually needed.

The next step is not more architecture. It is clearer failure evidence and better evaluation.
