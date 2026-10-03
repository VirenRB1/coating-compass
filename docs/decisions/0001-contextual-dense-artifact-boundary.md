# Decision 0001: contextual dense artifact boundary

- Status: accepted for implementation; hosted rollout pending owner approval
- Date: 2026-09-26

## Decision

Generate 50-100 approximate-token chunk contexts with Groq
`openai/gpt-oss-20b`, using the complete page-delimited PDF for each request. Store
the generated context separately from immutable manufacturer text, and embed
`context + original chunk` into a new Qdrant collection. Qdrant `page_content`
remains the original chunk, so the answer model and citations never treat generated
context as manufacturer evidence.

Chunk IDs derive from source hash, page, page-local offset, chunk settings, and
original text. They deliberately exclude the embedding model. A manifest and JSONL
checkpoints make generation resumable and reject stale source, prompt, or chunk
inputs before indexing.

## Alternatives and trade-offs

Using a document summary would reduce repeated prompt size but provide less precise
document context and would not exercise provider prefix caching. Storing contextual
text as page content would fit the default vector-store ingestion API, but risks
showing synthetic claims to the answer model. Direct Qdrant point insertion is a
little more code and preserves the evidence boundary.

Contextual BM25 is now implemented as a separate in-memory
experiment over the same validated records. Decision 0002 replaces handwritten
ranking with LangChain BM25Retriever while retaining the evidence boundary. It uses generated context plus original
text for ranking and returns only original text as evidence. Dense retrieval remains
the active application path; rank fusion and reranking remain separate experiments
so their effects can be measured independently.
