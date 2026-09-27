# Learning log

## 2026-09-26 — Contextual dense retrieval artifact boundary

### In my own words

Contextual retrieval gives an otherwise ambiguous chunk a short description of its
place in the complete document before embedding. That synthetic description helps
search, but it is not manufacturer evidence. The vector is created from the context
plus original text while answer generation receives only the original PDF text.

### Why stable IDs and a manifest matter

A chunk ID describes the source/chunk identity, so changing the embedding model must
not change it. The manifest records source hashes, chunk settings, prompt hash, and
completion counts. Indexing fails closed when any record is missing or stale instead
of silently mixing experiments.

### Alternatives and trade-offs

Full-document prompting supplies the strongest local context and can benefit from
Groq prefix caching when chunks are processed sequentially. It still costs one model
generation per chunk and repeats a large prefix. A document-summary prefix is
cheaper, but it adds another synthetic compression step and may omit local identity.

### Common failure modes

- A changed PDF hash means the immutable corpus no longer matches the manifest.
- A changed prompt makes old generated records stale.
- A partial run cannot build the contextual Qdrant collection.
- PDF extraction can warn about optional `fontTools`; verify extracted text before
  adding a dependency merely to silence warnings.

### Commands I can run

```powershell
uv run python -m src.data.contextualize_documents --dry-run
uv run python -m unittest tests/test_basic_rag_config.py
```

The non-dry-run command requires `--confirm-paid-calls` and provider credentials.

### Exercise / teach-back

Explain why generated context belongs in retrieval metadata but not in the evidence
shown to the answer model.

## 2026-09-26 — Full-pipeline RAG evaluation and GEval

### In my own words

A full-pipeline evaluation tests retrieval and answer generation together. This is
different from evaluating only whether the retriever found useful passages or only
whether an answer sounds good.

GEval asks a judge model to apply an explicit rubric to a test case. Coating Compass
uses it for qualities that require semantic judgment: simplicity and correctness.

### What problem it solves

Standard RAG metrics do not directly answer whether guidance is easy for a customer
to follow or whether it agrees with an acceptable reference answer. The two custom
rubrics make those expectations visible and reviewable.

### Alternatives and trade-offs

Exact string matching is cheap and deterministic but rejects valid alternative
wording. GEval handles semantic equivalence but costs model calls and can vary or
misjudge domain details. Deterministic coating safety checks remain necessary.

### Common failure mode

A short answer can appear simple while omitting an application limitation or safety
warning. The simplicity rubric therefore says that necessary qualifications must not
be penalized.

### Commands I can run

```powershell
uv run python -m unittest tests/test_full_pipeline_evaluation.py
uv run python -m src.evals.application_evals.evaluate_full_pipeline --label baseline
```

The second command uses hosted models and should run only with cost approval.

### Exercise / teach-back

Explain why faithfulness can be high while answer correctness is low.

## 2026-09-27 — Auditing synthetic retrieval context

### In my own words

Contextual text is useful for finding a chunk, but it is not manufacturer evidence.
The reliable boundary is therefore deterministic: verify every stored record against
the immutable PDF-derived chunk, then give the answer model only the original chunk.

### Evidence and trade-off

All 921 contextual records matched their source metadata and text. A representative
human review found relevant, grounded summaries and no unsupported numeric values,
but product identifiers were inconsistent and one legacy Groq record confused an
SDS section number with a page number. Regenerating the entire corpus now would cost
tokens without evidence that these imperfections hurt retrieval. Index version 1,
measure the known `manual_002` miss, and improve the prompt only if evaluation shows
that identity omissions matter.

### Common failure mode

Do not read the append-only provider logs as the finished dataset. They include
superseded failures from resumable attempts. Use the validated compact
`chunks.jsonl`, whose 921 records represent the latest successful result for each
stable chunk ID.

## 2026-09-26 — Fetching a versioned Langfuse prompt

### In my own words

A Langfuse prompt version is immutable, while a label is a movable pointer to one
version. Fetching by the `baseline` label lets the application identify the reviewed
baseline without hard-coding a numeric version.

### Current boundary

The prompt registry can fetch and validate the registered text prompt, but the RAG
graph does not consume it yet. Keeping retrieval separate from activation makes this
change easy to test and prevents a remote prompt from silently changing application
behavior in this increment.

### Activation increment

The RAG graph now requires prompt text as an explicit input. Application and
evaluation entry points fetch the `baseline` version and inject its text when they
construct the graph. Evaluation artifacts record the exact prompt version, and a
partial evaluation refuses to resume if that label has moved to another version.

### Common failure mode

`uv --system-certs` affects dependency downloads, not runtime HTTP clients. The
Langfuse fetch path injects the Windows trust store for networks with a private TLS
issuer and never disables certificate verification.

## 2026-09-26 — Reasoning tokens and empty answers

### In my own words

A reasoning model uses part of its completion budget before producing its visible
answer. If that budget is too small, a successful API response can still contain no
usable answer text.

### How it appears in this repository

GPT-OSS previously had a 700-token limit and default medium reasoning. The targeted
fix uses 2,000 tokens and low reasoning effort. `manual_002` then returned a complete
answer, although retrieval still supplied the wrong product evidence.

### Common mistake

Do not retry empty generations until one happens to pass and call that an evaluation
improvement. Change one recorded configuration variable, rerun the same case, and
keep retrieval failures distinct from generation failures.
