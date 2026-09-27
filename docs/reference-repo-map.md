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
