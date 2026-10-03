# Reference repository map

## Contextual dense retrieval

This milestone follows the project brief's controlled retrieval progression rather
than copying a reference-repository commit. It keeps the evaluated baseline store
intact, changes one retrieval variable, and creates an auditable artifact boundary
for a future retriever evaluation. The implementation is also inspired by
Anthropic's contextual-retrieval architecture, adapted to the existing Groq model
and coating-specific evidence rules. BM25 and reranking are postponed.

## Full-pipeline evaluation

| Reference | Disposition | Coating Compass adaptation |
|---|---|---|
| `e09d1d1` RAG metric examples | Adapt | Combine retrieval and generation metrics around the existing coating RAG graph. |
| `a3fea37` complete dataset evaluation with custom metrics | Adapt | Add explicit coating-aware GEval rubrics and paired JSON/Markdown artifacts. |

The reference repository's license is unspecified. Its architecture and commit intent
were used as learning references; source code, prompts, datasets, and artifacts were
not copied. The adapted layout keeps application evaluation under `src/evals/` and
reports under `reports/`, while retaining Coating Compass's existing models, corpus,
and metadata.

## Contextual BM25 retrieval

This increment follows Anthropic's published Contextual Retrieval architecture, not
a reference-repository source-code commit. It creates a lexical index from the same
generated context plus original chunk used by contextual dense retrieval, while
preserving original manufacturer text as the returned evidence. The implementation
is original, standard-library BM25; hybrid fusion and reranking are postponed until
the standalone retriever is evaluated.

## 2026-10-03 - Framework-first simplification

Owner-requested maintenance increment, not a new reference-commit reproduction.
Disposition: Adapt the framework approach already used for dense retrieval and the
LangGraph baseline. Replace original handwritten BM25 scoring with maintained
LangChain BM25Retriever/rank-bm25, replace embeddings HTTP plumbing, and consolidate
citation rendering. Keep coating evidence/identity/validation rules explicit.
Decision 0002 records the complete repository review and why domain-specific code
remains. No reference source, prompts, datasets, or artifacts copied. The owner
authorized committing this increment after offline verification.
The earlier standard-library BM25 entry describes v1; this increment supersedes it
with retrieval identity v2. Evaluation quality remains unmeasured for v2.
