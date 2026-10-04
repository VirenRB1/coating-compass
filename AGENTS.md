# Coating Compass agent instructions

Coating Compass is an unofficial, learning-first coating decision-support prototype grounded in
public manufacturer TDS and SDS documents. It is not endorsed by Dulux or PPG.

- Work in small, reviewable vertical slices and explain important concepts and trade-offs.
- Prefer deterministic validation and safety rules over LLM judgment.
- Prefer maintained LangChain and LangGraph components over handwritten infrastructure when they satisfy safety and evidence requirements. Keep custom code for coating-specific validation, original-only evidence boundaries, deterministic safety rules, and behavior unavailable from the frameworks. Choose the least code the owner can clearly explain.
- Treat PDFs under `data/dulux_canada_knowledge_sources/` as immutable source artifacts.
- Never commit manufacturer PDFs, secrets, generated embeddings, or vector-store files publicly.
- Preserve document hashes, page numbers, source URLs, and knowledge-base versions.
- Recommendations must support clarification, abstention, escalation, and page-level citations.
- Use hosted models only; do not download local ML model weights on this machine.
- Do not spend paid API credits, push, deploy, or change repository visibility without approval.
- Update relevant project, learning, decision, and session documentation with meaningful changes.
- Keep all documentation under `docs/` locally and continue updating it regularly; do not add it to Git. Do not add automated test files or generated test artifacts to Git unless the owner explicitly changes this preference.

Current commands:

- Install: `uv sync`
- Validate sources/contextual inventory (offline): `uv run python -m src.data.contextualize_documents --dry-run`
- Validate configuration (offline): `uv run python -m src.config`
- Ingest baseline (hosted embedding calls; approval required): set `retrieval.mode: baseline-dense` in `params.yaml`, then `uv run python main.py --ingest-only`
- Automated test files were removed at the owner's request; do not recreate or run tests unless requested.
- Lint: `uv tool run ruff check .` (use `uv --system-certs` on this Windows network)

Coating Advisor repository instructions

Required context

Before substantial work, read completely:

docs/Coating_Compass_Project_Brief.md

docs/Coating_Advisor_Reference_Repo_Codex_Handoff.md

the latest relevant entries in docs/reference-repo-map.md, docs/commit-plan.md, docs/learning-log.md, docs/session-log.md, and docs/decisions/ when those files exist.

Inspect the repository, Git status, current branch, recent history, README, dependency files, source tree, configuration, and tests before proposing changes. Preserve all unrelated user changes.

Project intent

This is a learning-first, unofficial Coating Advisor application. It converts plain-language painting projects into structured requirements, asks critical clarification questions, retrieves evidence from versioned manufacturer TDS/SDS documents, and recommends supported preparation-primer-topcoat systems with limitations, safety guidance, citations, uncertainty, and safe abstention.

Do not represent this project as manufacturer-approved.

Learning contract

For every meaningful change:

Explain the problem and concept in plain language.

Show the evidence that motivates the change.

Discuss the simplest implementation, alternatives, and trade-offs.

List expected file changes before editing.

Implement a small reviewable increment.

Run focused tests and report important results.

Explain the key code and commands the owner can run.

Record common failure modes and debugging steps.

Update the appropriate tracking and learning files.

End with a recap and optional teach-back exercise.

Do not silently build large features or hide failures with broad exception handling.

Reference-repository workflow

Use https://github.com/Himanshu-1703/llmops-rag-app as a learning reference only. Its license was unspecified when inspected, so do not copy its source code, prompts, data, notebooks, or artifacts.

For each relevant reference commit:

inspect and explain its intent and diff;

classify it as Reproduce, Adapt, Combine, Postpone, or Skip;

design an original Coating Advisor equivalent;

define acceptance criteria and tests;

update docs/reference-repo-map.md with the lesson, status, and our commit when applicable.

Do not imitate noisy CI-run commits or generated artifacts.

Domain and safety rules

Base product claims on the supplied manufacturer documents.

Treat raw TDS/SDS PDFs as immutable.

Keep source hashes, URLs, versions, page/section metadata, and knowledge-base versions reproducible.

Separate manufacturer facts, system inference, unknowns, and user assumptions.

Prefer deterministic compatibility, exclusion, and escalation rules where appropriate.

Ask for critical missing facts before recommending.

Recommend complete systems, not only a single product.

Cite document, page, section, and official URL when available.

Surface limitations and safety warnings prominently.

Abstain or escalate when the corpus does not support a safe answer.

Track unsafe recommendation rate, missed-warning rate, citation support, and appropriate abstention in addition to generic RAG metrics.

Engineering rules

Do not rebuild the completed baseline without evidence.

Prefer the smallest change that advances the current milestone.

Change one major experimental variable at a time.

Validate configuration and data schemas early.

Use `params.yaml` as the sole source of project-owned run settings, validated through
`src/config.py` before clients or output artifacts. Credentials and connection endpoints
remain in `.env`; do not restore model/tuning overrides through environment or CLI.
Preserve normalized parameter snapshots and hashes in evaluation reports. Changing
index model/chunking identity requires a new collection. Do not fabricate snapshots
for historical runs or resume runs with changed configuration.

Keep deterministic tests separate from paid or networked evaluations.

Never commit secrets, raw private data, local vector databases, tool caches, or transient run artifacts.

Keep raw manufacturer PDFs out of a public repository unless redistribution has been explicitly approved.

Do not add major dependencies, spend paid API credits, commit, push, deploy, or change repository visibility without owner approval.

Keep documentation aligned with behavior.

Use specific, educational commit messages and include tests with behavior changes.

Current priority

The basic RAG and controlled dense A/B evaluations are complete. The current owner-approved
increment centralizes validated YAML configuration and preserves experiment snapshots for
later MLflow integration. MLflow server/logging setup and BM25/hybrid paid evaluations remain
separate follow-up work requiring owner approval. Keep docs local and do not recreate tests.
