Master Context for Codex: AI Coating Advisor

Use this document as the durable project brief for a new repository. Read it fully before changing code. The project is intentionally both a portfolio-quality AI application and a structured learning environment. The owner wants to understand how to build systems like this independently in the future, not merely receive finished code.

1. Project identity

Working name: Coating Advisor

Suggested repository name: coating-advisor

Do not present this as an official Dulux or Pittsburgh Paints Company application. It is an unofficial learning and portfolio prototype that uses publicly available manufacturer documentation. Preserve manufacturer attribution and source links.

One-sentence product definition

Build an evidence-based coating recommendation assistant that translates a customer's plain-language project description into technical coating requirements, identifies missing critical information, retrieves relevant evidence from manufacturer Technical Data Sheets and Safety Data Sheets, and recommends suitable primer-and-paint systems with preparation, application, limitation, safety, and source guidance.

Why this project exists

Customers describe paint projects in everyday language, but the information needed to recommend a suitable coating is distributed across technical documents and expressed using specialist terminology. A customer might say:

I need paint for an old bathroom wall that gets steamy, already has paint on it, and needs to be washable.

The system must translate that into requirements such as:

interior application;

previously coated substrate;

high humidity;

washability and stain resistance;

possible mildew risk;

surface preparation and adhesion checks;

an appropriate primer only if the surface condition requires it.

This is not meant to be another generic "chat with PDFs" application. Retrieval is infrastructure inside a decision-support product.

Domain advantage

The project owner has approximately four years of experience working in the paint industry at Dulux. Treat that experience as a core project asset. The owner should provide anonymized real-world scenarios, expected clarifying questions, common mistakes, and practical product-selection knowledge. Do not override that knowledge casually. When product documents and domain experience appear inconsistent, surface the inconsistency and investigate it.

2. Primary goals

Build a useful coating-selection assistant for basic interior and exterior projects.

Learn the complete engineering process from an empty repository to a tested and deployed AI application.

Establish a traditional RAG baseline before adding contextual retrieval.

Experimentally compare raw, metadata-aware, contextual, hybrid, and reranked retrieval.

Evaluate recommendation quality, retrieval quality, citation support, abstention, and safety.

Grow the same application alongside an LLMOps course instead of creating many disconnected tutorial repositories.

Produce a repository that demonstrates domain expertise, RAG, evaluation, experimentation, observability, backend engineering, testing, CI/CD, and deployment.

3. Learning contract

This is a learning-first project. Do not silently build large features on the owner's behalf.

For every meaningful feature or technical decision:

Explain the problem in plain language.

Explain the relevant concept and where it fits in the architecture.

Present the simplest reasonable implementation.

Mention one or two realistic alternatives and why they are not being selected now.

State the trade-offs of the chosen approach.

Show which files will change before changing them.

Implement in a small, reviewable increment.

Run focused tests and show the important results.

Walk through the important code at the function and data-flow level.

Provide commands the owner can run independently, with expected results.

Describe at least one common failure mode and how to diagnose it.

End each milestone with a short recap and a small optional exercise or teach-back question.

Do not dump a complete complex system into the repository in one step. Prefer vertical slices that work end to end. The owner should be able to explain every major dependency, abstraction, schema, and evaluation metric used in the project.

When introducing terminology such as embeddings, cosine similarity, chunk overlap, reciprocal rank fusion, reranking, calibration, migrations, tracing, or evaluation gates, add a concise explanation to the learning notes.

4. Safety and product-behaviour principles

The application is decision support, not an unrestricted product recommender.

It must be able to:

ask for critical missing details before recommending;

return more than one suitable option when the documents do not support a single best answer;

say that it lacks enough evidence;

say that no product in the current catalog is supported;

recommend escalation to manufacturer technical service for specialized or high-risk applications;

distinguish manufacturer-supported facts from system inference;

cite the supporting TDS or SDS page and section;

show limitations and contraindications prominently;

avoid inventing compatibility, coverage, preparation, drying, recoating, temperature, or safety claims.

False confidence is more harmful than abstention. Do not optimize only for answer rate. Track unsafe recommendation rate and missed-warning rate.

Never reveal private chain-of-thought. Return concise reasons, structured evidence, citations, uncertainty, and decision factors instead.

5. Confirmed first knowledge-source collection

The initial corpus contains 18 product families and 36 English-Canada PDFs: one TDS and one SDS for each selected SKU. The documents were downloaded from the official Dulux Canada product catalog on 2026-09-19 and validated as readable PDFs. A CSV and JSON manifest record source URLs, selected variants, document metadata, SDS revision dates, and SHA-256 hashes.

Expected source package:

Dulux_Canada_Knowledge_Sources_v1.zip

Expected contents:

18 TDS PDFs;

18 SDS PDFs;

manifest.json;

manifest.csv;

README.md.

If the archive or manifests are not present in the repository, ask the owner to place them in a local import directory. Do not search unrelated directories or download a new corpus without discussing the change.

Selected products

#

Product family

SKU

Selected finish/base

1

Dulux Ultra Interior

949000/01

Eggshell, white and pastel base

2

Dulux X-PERT Interior

14010A/01

Eggshell, white and pastel base

3

Dulux Lifemaster Interior

59311A/01

Eggshell, white and pastel base

4

Dulux Diamond Interior

151100/01

Eggshell, white and pastel base

5

Dulux Kitchen and Bath

18010A/01

Eggshell, white and pastel base

6

Dulux X-PERT Waterborne Alkyd

22010/01

Melamine, white and pastel base

7

Dulux Anti-Scuff Interior

55110/01

Low-sheen eggshell, white and pastel base

8

Dulux Water-based Floor Enamel

247010/01

Satin, white and pastel base

9

Dulux Weatherguard Exterior

1530/01

Flat/matt, white and pastel base

10

Dulux Diamond Exterior

16330/01

Flat, white and pastel base

11

Dulux Weatherguard Exterior Primer

1535/01

Flat, ready-mix white

12

Dulux Gripper Interior/Exterior Primer

60000A/01

Flat, ready-mix white

13

Dulux Lifemaster Interior Primer

59113/01

Flat, white and pastel base

14

Dulux X-PERT Interior Primer

11000/01

Flat, white and pastel base

15

Dulux Ultra Classic Interior Primer

36600/01

Flat, white and pastel base

16

Dulux Ultra Classic Ceiling Paint

7700/01

Flat, white and pastel base

17

Dulux Lifemaster Interior Ceiling Paint

59170/01

Flat, white and pastel base

18

Dulux X-PERT Interior Ceiling Paint

12170/01

Flat, ready-mix white

The two specialty products without an eggshell option use the closest relevant manufacturer-listed finish: Melamine for X-PERT Waterborne Alkyd and Satin for Water-based Floor Enamel.

Source-data rules

Treat downloaded PDFs as immutable source artifacts.

Never rewrite, optimize, or overwrite an original source PDF.

Preserve the original filename, source URL, retrieval date, checksum, document type, SKU, base, finish, and revision information.

Store generated text, chunks, embeddings, and contextual summaries separately from raw documents.

Detect duplicate documents by content hash, not filename alone.

A newer TDS/SDS must not silently replace an older version. Record supersession and preserve reproducibility of past experiments.

Do not commit manufacturer PDFs to a public Git repository by default. Track the manifest, hashes, ingestion code, and reproduction instructions. Keep raw documents in a gitignored local data directory unless the owner explicitly confirms that redistribution is permitted.

A monthly task already exists to check the 18 product pages for TDS/SDS updates. Design the ingestion pipeline so a future refresh can compare hashes, identify changed documents, reprocess only affected products, run regression evaluations, and publish a new knowledge-base version.

6. V0 scope

Build a small, complete baseline before contextual retrieval or production infrastructure.

V0 must support

basic interior wall projects;

basic exterior wall/siding projects covered by the selected products;

ceilings;

primers and common preparation needs;

kitchens and bathrooms;

high-traffic/scuff-resistant interior needs;

trim/furniture only where X-PERT Waterborne Alkyd documentation supports the use;

concrete or wood floors only where the Floor Enamel documentation supports the use;

manufacturer-supported application and safety guidance;

citations to document, page, and section.

V0 interaction

The user provides a plain-language project description. The system should extract or ask for relevant facts such as:

interior or exterior;

substrate/material;

bare, new, or previously coated surface;

current coating type if known;

room or environment;

moisture/humidity exposure;

traffic and expected wear;

cleaning or washability needs;

desired finish;

surface condition, stains, mildew, peeling, chalking, rust, or contamination;

application method;

approximate temperature and ventilation when relevant;

project area when quantity estimation is introduced.

If enough information is available, V0 returns one to three candidate systems. A system can contain surface preparation, optional primer, and topcoat rather than merely naming one can of paint.

Suggested response structure

Project understanding
Missing or assumed details

Recommended coating system
1. Surface preparation
2. Primer, if required
3. Topcoat and number of coats

Why this system fits
Application requirements
Important limitations
Safety considerations
Alternative products
Confidence and escalation status
Sources: document, page, section, official URL

V0 non-goals

Do not initially build:

the full Dulux/PPG catalog;

an autonomous agent;

LangGraph workflows merely for demonstration;

Kubernetes or microservices;

OCR or multimodal retrieval;

fine-tuning;

live store inventory;

live pricing;

automated web crawling of the whole manufacturer site;

chemical-immersion, tank-lining, industrial-floor, or other high-risk recommendations outside the corpus;

a public application represented as manufacturer-approved.

7. Architecture principles

Core rule

Use an LLM for language understanding and evidence-based synthesis, not as the sole source of product truth.

The high-level flow is:

Customer description
        |
        v
Structured project requirements
        |
        v
Missing-critical-information check
   |                 |
   v                 v
Clarifying question  Candidate retrieval
                         |
                         v
                 TDS/SDS evidence
                         |
                         v
              Deterministic constraints
                         |
                         v
                 Candidate ranking
                         |
                         v
        Recommendation or safe abstention
                         |
                         v
          Guidance + limitations + citations

Separate stable and volatile data

Technical documentation belongs in the retrieval knowledge base. Volatile commercial data does not.

Do not embed prices, promotions, or inventory as permanent RAG knowledge. When those features are introduced, resolve a recommended SKU against a separate structured catalog or API. During development, a small mock CSV or database table is acceptable.

Metadata establishes identity; context establishes meaning

Every chunk must already carry deterministic identity metadata such as product family, SKU, document type, document revision, page, and section. Contextual retrieval must not be used merely to recover a product name that metadata should provide.

Contextual retrieval should add semantic context. For example, a chunk saying "Apply only when air and surface temperatures are..." may receive a prefix explaining that it belongs to a particular exterior flat coating and that the section defines application conditions. Keep the original chunk and generated context separately so experiments are reproducible.

8. Recommended technical direction

Use these as starting defaults, not permanent dogma. Record any change as a decision.

Language and packaging

Python 3.11 or 3.12.

uv for environment and dependency management when available.

pyproject.toml as the package and tool configuration source.

src/ package layout.

Type hints for public functions and core data structures.

Pydantic models for validated application schemas.

Core libraries

PDF extraction: begin with PyMuPDF or pypdf; compare only if extraction quality creates a measured problem.

Data validation: Pydantic.

Embeddings: a free CPU-friendly Hugging Face sentence-transformer, initially something in the size class of BAAI/bge-small-en-v1.5.

Vector index: begin with a simple local option such as FAISS or Chroma. Choose one after explaining persistence, metadata-filtering, and portability trade-offs.

Keyword retrieval: BM25 only after a baseline exists.

Reranking: add only after retrieval evaluation shows a need.

Application API: FastAPI after the retrieval core works through a CLI or test harness.

UI: defer the choice until the core behaviour is stable. A simple frontend is preferable to a visually polished but unreliable chatbot.

Evaluation: DeepEval for selected LLM/RAG metrics plus deterministic information-retrieval metrics implemented transparently.

Experiment tracking: MLflow when multiple meaningful configurations exist.

Runtime tracing and prompt management: Langfuse later, with sensitive document content redacted or disabled where appropriate.

Containers: Docker after a working local baseline.

CI: GitHub Actions after tests and evaluation subsets exist.

LangChain may be used for useful integrations, but keep domain models and core logic independent of framework-specific classes. Do not introduce LangGraph until the workflow genuinely needs explicit state, branching, resumption, or durable orchestration.

Resource constraints

Development should prefer free/local components. The owner's laptop has approximately 7.8 GB of RAM and a GTX 1650 with 4 GB VRAM. Embeddings should run on CPU. Do not assume vLLM is viable locally. Use paid APIs only deliberately, keep providers configurable, and record costs. The previous target for paid final experiments was approximately USD $10, so protect that budget unless the owner revises it.

9. Canonical data model

Define schemas before building the index. Exact field names may evolve through ADRs, but preserve these concepts.

Product

{
  "product_id": "dulux-xpert-interior-14010a",
  "manufacturer": "Dulux Canada",
  "product_family": "Dulux X-PERT Interior",
  "sku": "14010A/01",
  "category": "interior_paint",
  "finish": "eggshell",
  "base": "white_and_pastel",
  "active": true
}

Source document

{
  "document_id": "sha256-or-stable-derived-id",
  "product_id": "dulux-xpert-interior-14010a",
  "document_type": "TDS",
  "language": "en-CA",
  "revision_date": null,
  "downloaded_at": "2026-09-19T00:00:00Z",
  "source_url": "official URL",
  "original_filename": "...pdf",
  "sha256": "...",
  "supersedes_document_id": null,
  "active": true
}

Extracted section

{
  "section_id": "stable-id",
  "document_id": "...",
  "heading": "Application Conditions",
  "page_start": 1,
  "page_end": 2,
  "text": "original extracted section text",
  "extraction_method": "pymupdf"
}

Chunk

{
  "chunk_id": "stable-id",
  "document_id": "...",
  "product_id": "...",
  "document_type": "TDS",
  "section_heading": "Application Conditions",
  "page_start": 1,
  "page_end": 1,
  "chunk_index": 3,
  "original_text": "...",
  "context_prefix": null,
  "retrieval_text": "...",
  "token_count": 412,
  "embedding_model": "...",
  "kb_version": "v0.1"
}

Structured project request

{
  "location": "interior",
  "space": "bathroom",
  "substrate": "drywall",
  "surface_state": "previously_coated",
  "existing_coating": "unknown",
  "moisture_exposure": "high_humidity",
  "traffic": "normal",
  "washability_needed": true,
  "desired_finish": "eggshell",
  "application_temperature_c": null,
  "known_problems": ["possible_mildew"],
  "missing_critical_fields": ["mildew_status", "coating_condition"]
}

Recommendation result

{
  "status": "needs_clarification",
  "clarifying_questions": ["Is there active mildew, or only old staining?"],
  "recommended_systems": [],
  "unsupported_or_rejected_products": [],
  "evidence": [],
  "warnings": [],
  "confidence": null,
  "escalation_required": false
}

Do not encode confidence as an arbitrary percentage until it has a defensible definition and calibration method.

10. Ingestion design

Build ingestion as a deterministic, repeatable pipeline:

manifest + immutable PDFs
        -> validate hashes and metadata
        -> extract page text
        -> identify document sections
        -> normalize conservatively
        -> create page/section-aware chunks
        -> attach deterministic metadata
        -> embed retrieval text
        -> build versioned index
        -> run ingestion tests and corpus report

Requirements:

fail clearly when a PDF is missing or its checksum differs;

preserve page boundaries for citations;

preserve lists, limitations, preparation instructions, and tables as accurately as possible;

avoid aggressive cleaning that deletes negations, symbols, ranges, units, or warning language;

keep TDS and SDS document types distinguishable;

avoid merging unrelated sections merely to reach a target chunk size;

use stable IDs so repeated ingestion of unchanged inputs is idempotent;

write an ingestion report with page counts, extracted character counts, sections, chunks, skipped content, and errors;

test the pipeline first on two contrasting products before processing all 36 documents.

Start with section-aware recursive chunking. Record chunk size and overlap in configuration rather than hard-coding them. Do not introduce semantic chunking until a baseline and evidence show it is useful.

11. Retrieval progression and experiments

Implement retrieval configurations in a controlled sequence against the same benchmark.

A. Baseline dense retrieval

Embed original chunks and retrieve the nearest chunks. Include deterministic product/document metadata in returned results but not in the text sent to the embedding model beyond the agreed baseline.

B. Metadata-aware retrieval

Use extracted project requirements to apply safe metadata filters or boosts, such as interior/exterior and product category. Never filter on uncertain fields as if they were facts.

C. Contextual retrieval

Generate a concise context prefix for each chunk using the full document or a reliable document summary. Cache results. Store:

original text;

context prefix;

combined retrieval text;

model and prompt version;

generation timestamp;

token usage and cost;

source document hash.

Compare against the raw baseline. Do not assume contextual retrieval wins.

D. Hybrid retrieval

Combine dense retrieval with BM25. Define the fusion method explicitly, preferably Reciprocal Rank Fusion for the first transparent implementation. Explain why exact product names, SKUs, substrate terms, and phrases can benefit from keyword retrieval.

E. Reranked retrieval

Retrieve a larger candidate set and rerank it to a smaller final set. Measure quality, latency, and resource cost. Do not add a reranker only because it is common in RAG diagrams.

Experiment variables

Track at least:

chunk size and overlap;

section-aware versus simpler chunking;

embedding model;

query formulation;

metadata filters/boosts;

raw versus contextualized chunks;

context-generation prompt/model;

dense top-k;

BM25 top-k;

hybrid fusion parameters;

reranker model and candidate count;

final evidence count;

generator model and prompt version;

latency and cost.

12. Clarification and recommendation logic

The clarification engine is a primary feature, not a cosmetic pre-chat form.

Define critical fields by project category. Examples:

Interior wall: substrate, current surface condition, room/moisture, existing coating when relevant, required durability.

Exterior: substrate, current coating condition, chalking/peeling, weather exposure, application temperature.

Floor: concrete or wood, bare or coated, contamination, moisture, traffic, intended use.

Trim/furniture: substrate, current coating, adhesion concerns, desired finish, ventilation/application constraints.

Use a deterministic validation layer after LLM extraction. The LLM can propose structured fields, but Pydantic and domain rules decide whether required information is missing.

Candidate product retrieval and evidence collection must be separated from final recommendation generation. The final model should receive only relevant evidence and explicit constraints.

Represent contraindications and escalation rules explicitly where possible. Examples include unsupported substrates, use cases outside the current corpus, insufficient ventilation information for a relevant safety concern, or uncertainty about an existing coating that affects adhesion.

13. Evaluation strategy

Evaluation is part of the product, not a final decoration.

Benchmark dataset

Create 30-50 realistic, anonymized customer scenarios for the initial catalog. Start with 10 carefully reviewed scenarios before scaling. Each scenario should include:

plain-language customer request;

structured ground-truth project facts;

critical missing facts;

expected clarifying questions;

acceptable product systems;

unacceptable products and the reason;

required warnings or limitations;

supporting document IDs/pages/sections;

whether escalation or abstention is expected.

The owner should review the scenarios using domain experience. Avoid using real customer information.

Retrieval metrics

Recall@K;

Precision@K;

Mean Reciprocal Rank;

nDCG where graded relevance is available;

DeepEval contextual recall;

DeepEval contextual precision;

contextual relevancy where appropriate.

Generation metrics

faithfulness;

answer relevancy;

citation correctness;

citation completeness;

unsupported-claim rate;

required-detail coverage.

Recommendation and safety metrics

acceptable-system accuracy;

correct product-family rate;

correct primer decision;

substrate compatibility accuracy;

expected clarification recall;

unsafe recommendation rate;

missed critical warning rate;

unsupported safety claim rate;

appropriate abstention/escalation rate.

Prefer deterministic tests and expert labels for high-risk properties. Use an LLM judge only where a semantic judgment is genuinely required, and inspect judge disagreements manually.

Create a small, inexpensive regression subset for CI and a larger offline benchmark for experiments.

14. LLMOps and production growth path

Add these only when the previous stage is working and measurable.

Baseline RAG with citations.

Evaluation dataset and deterministic retrieval metrics.

Structured requirement extraction.

Clarification engine.

Contextual retrieval A/B experiment.

Hybrid retrieval and reranking if justified.

Langfuse prompt versioning and runtime traces.

MLflow experiment tracking.

Knowledge-base versioning and document refresh workflow.

Evaluation gates in CI.

FastAPI service and user interface.

Docker packaging.

Deployment, health checks, structured logging, monitoring, and rollback.

Separate price/inventory service.

Give each tool one clear responsibility:

Tool

Primary responsibility

DeepEval

Offline RAG/generation evaluation

Langfuse

Runtime LLM tracing and prompt management

MLflow

Experiment parameters, metrics, artifacts, and comparisons

Git

Source and documentation history

Vector index/database

Retrieval data

Application database

Products, projects, feedback, KB versions

GitHub Actions

Tests and evaluation gates

Docker

Reproducible runtime packaging

Avoid duplicating evaluation, prompt registry, and tracing ownership across every tool.

15. Repository structure

Begin lean and allow the structure to grow. A target shape is:

coating-advisor/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── configs/
│   ├── base.yaml
│   ├── retrieval/
│   └── experiments/
├── data/
│   ├── README.md
│   ├── manifests/
│   ├── raw/                 # gitignored manufacturer PDFs
│   ├── processed/           # gitignored generated data
│   └── evals/
├── src/coating_advisor/
│   ├── config.py
│   ├── domain/
│   │   ├── models.py
│   │   ├── rules.py
│   │   └── taxonomy.py
│   ├── ingestion/
│   │   ├── manifest.py
│   │   ├── pdf_extract.py
│   │   ├── sections.py
│   │   ├── chunking.py
│   │   └── pipeline.py
│   ├── retrieval/
│   │   ├── interfaces.py
│   │   ├── dense.py
│   │   ├── bm25.py
│   │   ├── hybrid.py
│   │   └── rerank.py
│   ├── understanding/
│   │   ├── extract_requirements.py
│   │   └── clarification.py
│   ├── recommendation/
│   │   ├── candidates.py
│   │   ├── constraints.py
│   │   └── generate.py
│   ├── evaluation/
│   ├── observability/
│   ├── api/
│   └── cli.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   └── fixtures/
├── experiments/
│   ├── README.md
│   └── results/             # generated outputs may be gitignored
├── docs/
│   ├── project-context.md
│   ├── architecture.md
│   ├── roadmap.md
│   ├── data-catalog.md
│   ├── evaluation-plan.md
│   ├── safety.md
│   ├── glossary.md
│   ├── troubleshooting.md
│   ├── learning-log.md
│   ├── session-log.md
│   └── decisions/
│       ├── README.md
│       └── ADR-0001-*.md
└── .github/workflows/

Do not create empty directories and dozens of placeholder files on day one. Create files when their purpose becomes real, while preserving the intended organization.

16. Agentic coding and knowledge-tracking files

Maintaining project memory is mandatory. Update relevant files as part of the same change that introduces the information. Do not wait for the user to ask repeatedly.

AGENTS.md

Keep only durable instructions and facts that future coding agents must know, such as:

project purpose and safety posture;

learning-first collaboration rules;

source-data immutability;

commands for setup, tests, linting, ingestion, and evaluation;

repository conventions;

current architectural boundaries;

resource/cost constraints;

requirement to update documentation after meaningful changes;

instructions not to commit raw manufacturer PDFs publicly;

instructions not to push, deploy, or spend paid API funds without authorization.

Do not turn AGENTS.md into a diary or duplicate the README.

docs/project-context.md

Store the product problem, users, scope, business hypotheses, domain boundaries, and confirmed requirements. Update when the product definition changes.

docs/architecture.md

Describe components, data flow, interfaces, and deployment shape. Include small Mermaid diagrams only when they improve understanding. Update it when the actual architecture changes, not merely when ideas are discussed.

Architecture Decision Records

Use docs/decisions/ADR-NNNN-short-title.md for decisions with meaningful alternatives or future consequences. Each ADR should include:

Status
Date
Context/problem
Evidence
Options considered
Decision
Why
Consequences
Trade-offs
Revisit trigger
Related experiments/issues

Example decisions include vector-store choice, PDF extraction library, chunking strategy, embedding model, introduction of BM25, contextualization model, and privacy settings for traces.

docs/learning-log.md

Maintain a chronological learning record. Each entry should contain:

concept learned;

plain-language explanation;

how the project uses it;

small code example or link to the implementing file;

alternative considered;

common mistake;

question the owner should now be able to answer.

docs/session-log.md

At the end of every substantial Codex session, append:

date;

session goal;

changes completed;

tests run and results;

decisions made or ADRs created;

files changed;

known issues;

exact next recommended step.

This is the handoff for the next agent/session. Keep it concise and factual.

docs/roadmap.md

Track milestones, current status, dependencies, acceptance criteria, and deferred ideas. Clearly separate Now, Next, and Later so the project does not expand uncontrollably.

docs/data-catalog.md

Track every source product, SKU, TDS/SDS document, revision/date, checksum, active/superseded state, ingestion state, and knowledge-base version. The machine-readable manifest remains authoritative for automation; this document explains it to humans.

docs/evaluation-plan.md

Define benchmark design, labels, metrics, judge prompts, thresholds, known limitations, and how to reproduce each evaluation.

docs/troubleshooting.md

Record problems only after they occur and are understood. Include symptom, root cause, diagnostic commands, resolution, and prevention. Avoid speculative clutter.

Experiment records

Every meaningful experiment should have a unique ID and immutable configuration. Record:

hypothesis;

code and knowledge-base versions;

dataset version;

parameters;

models/prompts;

metrics;

latency/cost;

qualitative failures;

conclusion;

resulting decision or next experiment.

Use MLflow later, but keep a human-readable experiment index in the repository.

Optional project-specific agent skills

Do not create skills merely to appear agentic. After a workflow has been performed and stabilized at least twice, consider reusable skills for:

validating and ingesting a new TDS/SDS release;

running the retrieval benchmark;

comparing two experiment configurations;

generating a session handoff;

reviewing recommendation safety and citations.

If skills are created, use the official skill-creation workflow, validate them, version them in Git, and document when they should and should not run.

17. Testing expectations

Unit tests

manifest parsing and checksum validation;

stable ID generation;

schema validation;

section detection;

chunk metadata and page ranges;

critical-field detection;

deterministic compatibility and escalation rules;

citation formatting;

configuration loading.

Integration tests

two sample PDFs through extraction and chunking;

index creation and retrieval;

a question producing evidence with valid citations;

structured extraction followed by clarification;

recommendation generation constrained to retrieved evidence.

Regression tests

known queries continue to retrieve expected documents;

required warnings are not dropped;

unsafe scenarios abstain or escalate;

citations refer to existing document/page pairs;

unchanged documents produce stable IDs and no duplicate chunks.

Quality tools

Choose a small, understandable set such as pytest, ruff, and a type checker. Explain each tool before adding it. Avoid overlapping formatters and linters without a reason.

18. Privacy, licensing, and security

Use only public manufacturer documentation unless explicit permission exists for internal sources.

Do not store customer names, addresses, account information, or real conversations in examples.

Anonymize scenarios derived from work experience.

Do not expose API keys in files, logs, notebooks, traces, or screenshots.

Use .env.example with fake values and validate configuration at startup.

Configure Langfuse or any future observability system to avoid capturing full sensitive prompts/documents by default.

Link to official sources rather than presenting copied documents as project-owned content.

Include an unofficial-prototype disclaimer in the README and user interface.

Do not claim safety certification, manufacturer approval, revenue improvement, reduced returns, or recommendation accuracy without measured evidence.

19. Business hypotheses to evaluate

Treat these as hypotheses, not claims:

reduce incorrect product recommendations;

reduce returns or reimbursements caused by unsuitable advice;

reduce time spent researching difficult projects;

reduce unnecessary escalation for routine questions;

improve recommendation consistency;

improve associate confidence;

improve conversion on complex projects;

improve attachment recommendations for primer and preparation products.

Eventually define a pilot measurement plan rather than relying only on offline model metrics.

20. Definition of done for the first baseline milestone

The first baseline is complete only when:

The repository installs from documented commands in a clean environment.

The manifest and 36 PDFs are validated without modifying the source files.

Two sample products can be ingested end to end, followed by the complete corpus.

Every chunk has product, SKU, document type, page, section, document hash, and KB-version metadata.

A CLI or test harness accepts a project question.

Baseline dense retrieval returns inspectable evidence.

The answer contains supported guidance and document/page citations.

The system can abstain when the corpus does not support an answer.

Unit and integration tests pass.

A small set of at least 10 reviewed scenarios produces baseline metrics.

Setup, architecture, data, decisions, learning notes, and session handoff are current.

The owner can explain the complete path from PDF to chunk to embedding to retrieval to cited answer.

Freeze and tag this configuration as the traditional-RAG baseline before implementing contextual retrieval.

21. First Codex assignment

Do not begin by writing the whole application. Start with repository discovery and a proposed bootstrap plan.

Step 1: inspect safely

Inspect the current directory and Git state.

Read any existing AGENTS.md, README, project notes, manifests, and configuration.

Locate the Dulux source archive or manifests without modifying them.

Report existing user changes and avoid overwriting unrelated work.

Step 2: restate understanding

Summarize:

the user problem;

V0 scope and non-goals;

learning requirements;

safety rules;

available data;

the smallest useful first vertical slice.

List uncertainties separately. Ask only questions that materially affect the first slice.

Step 3: propose the first small milestone

Recommend an initial milestone such as:

Bootstrap the Python repository, validate the manifest and PDF hashes, define the Product/SourceDocument models, and ingest two sample TDS/SDS pairs into page-aware extracted JSON—without embeddings yet.

Explain why this comes before vector search.

Step 4: create only essential tracking files

After the owner agrees, create or update:

AGENTS.md;

README.md;

docs/project-context.md;

docs/roadmap.md;

docs/learning-log.md;

docs/session-log.md;

docs/decisions/README.md;

the first ADRs only for decisions actually made;

data/README.md and safe .gitignore rules.

Do not generate empty documentation for future tools.

Step 5: implement and teach

Implement the agreed slice with tests. Explain each new dependency, schema, and command. Update the tracking files in the same session. Finish with:

what now works;

test evidence;

what the owner learned;

remaining risks;

one recommended next step;

one optional exercise the owner can attempt.

22. Working rules for Codex

Prefer the smallest change that moves the current milestone forward.

Do not add architecture for hypothetical scale before measuring a problem.

Do not hide failures with broad exception handling or silent fallbacks.

Do not replace deterministic checks with an LLM call.

Do not change models, prompts, chunking, and retrieval settings simultaneously in an experiment.

Keep configurations reproducible and seeds fixed where applicable.

Never modify or delete raw TDS/SDS files.

Do not spend paid API credits without asking first and estimating the cost.

Do not push, deploy publicly, or change repository visibility without explicit authorization.

Do not use proprietary work data or customer information.

Preserve existing user changes in a dirty worktree.

Prefer focused tests after each change and a broader suite before milestone completion.

Update documentation when facts or decisions change; do not let documentation drift.

When unsure about a product claim, return to the source documents.

When unsure about project intent, ask rather than silently widening scope.

23. Desired final portfolio story

The eventual project should support a truthful description similar to:

I built an AI coating-specification assistant that translates natural-language project descriptions into technical coating requirements and recommends evidence-backed coating systems from manufacturer TDS/SDS documentation. I created an evaluation benchmark from realistic coating scenarios, compared baseline retrieval against metadata-aware, contextual, hybrid, and reranked retrieval, added safety and recommendation regression tests, versioned prompts and knowledge bases, tracked experiments, implemented observability and CI evaluation gates, integrated structured commercial data separately from technical RAG, and deployed the evaluated system as a production service.

Reach this story through measured, documented increments. Do not imitate the final architecture before the baseline has earned each component.
