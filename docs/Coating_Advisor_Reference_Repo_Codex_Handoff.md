# Coating Advisor: Codex Handoff and Reference-Repository Development Guide

This document is durable context for a Codex coding session working on the **Coating Advisor** project. It explains the project, the learning-first working agreement, how to use the reference repository, how to translate its commit history into this domain, what files must record the work, and exactly what the next development milestone should be.

Read this document together with:

- `docs/Coating_Compass_Project_Brief.md` — the full product, domain, safety, data, architecture, and learning brief;
- the current repository's root `AGENTS.md` — the short, always-active operating rules;
- the current repository's `README.md`, source tree, tests, Git status, and Git history;
- `docs/reference-repo-map.md`, `docs/commit-plan.md`, `docs/learning-log.md`, `docs/session-log.md`, and `docs/decisions/`, once they exist.

The detailed brief and this handoff are source-of-truth project documents. `AGENTS.md` should remain concise and point to them rather than duplicating all of their content.

---

## 1. Instruction to the Codex session

You are helping build this project as a technical mentor and implementation partner. The owner has completed a basic RAG implementation and now wants to improve it through small, understandable, evidence-backed commits.

Your job is not to copy another repository or to rush to its final architecture. Your job is to:

1. inspect the owner's current implementation;
2. establish what already works with tests and evidence;
3. study one useful concept or commit from the reference repository at a time;
4. explain the concept and why it exists;
5. decide whether it should be reproduced, adapted, combined, postponed, or skipped;
6. design the Coating Advisor equivalent;
7. implement one small reviewable increment only after agreement;
8. test it;
9. record what changed and what the owner learned;
10. preserve a clean, educational Git history.

Do not assume that this chat, another Codex session, or the reference repository is automatically available. Read the files in the current repository and inspect the repository state at the beginning of every session.

---

## 2. Project identity and current state

### Working name

**Coating Advisor**

### Product definition

Coating Advisor is an unofficial learning and portfolio application that converts a customer's plain-language painting project into structured technical requirements, asks for critical missing information, retrieves evidence from manufacturer Technical Data Sheets (TDS) and Safety Data Sheets (SDS), and recommends a supported coating system consisting of preparation, primer when required, and topcoat.

It is not an official Dulux or Pittsburgh Paints Company product. It must preserve source attribution and must not imply manufacturer approval.

### Current project state

- The owner reports that the **basic RAG implementation is complete**.
- Do not rebuild the baseline from scratch unless inspection demonstrates that a missing foundation prevents the next milestone.
- First inspect the code, tests, configuration, Git history, and current behavior.
- Freeze important baseline behavior with tests or a reproducible evaluation before making large retrieval or prompting changes.
- The next major educational theme should be **evaluation**, beginning with a small human-reviewed coating benchmark.

### Initial knowledge base

The first corpus contains 18 Dulux Canada product families and 36 English-Canada PDFs: one TDS and one SDS per selected SKU. A companion source package and manifests have already been assembled. The finish-selection rule used for source collection was:

- eggshell for ordinary interior paints;
- flat for exterior paints;
- flat for primers and ceiling paints;
- the closest relevant listed specialty finish when eggshell was not offered: Melamine for X-PERT Waterborne Alkyd and Satin for Water-based Floor Enamel.

The initial products are:

| # | Product family | SKU | Selected finish/base |
|---:|---|---|---|
| 1 | Dulux Ultra Interior | `949000/01` | Eggshell, white and pastel base |
| 2 | Dulux X-PERT Interior | `14010A/01` | Eggshell, white and pastel base |
| 3 | Dulux Lifemaster Interior | `59311A/01` | Eggshell, white and pastel base |
| 4 | Dulux Diamond Interior | `151100/01` | Eggshell, white and pastel base |
| 5 | Dulux Kitchen and Bath | `18010A/01` | Eggshell, white and pastel base |
| 6 | Dulux X-PERT Waterborne Alkyd | `22010/01` | Melamine, white and pastel base |
| 7 | Dulux Anti-Scuff Interior | `55110/01` | Low-sheen eggshell, white and pastel base |
| 8 | Dulux Water-based Floor Enamel | `247010/01` | Satin, white and pastel base |
| 9 | Dulux Weatherguard Exterior | `1530/01` | Flat/matt, white and pastel base |
| 10 | Dulux Diamond Exterior | `16330/01` | Flat, white and pastel base |
| 11 | Dulux Weatherguard Exterior Primer | `1535/01` | Flat, ready-mix white |
| 12 | Dulux Gripper Interior/Exterior Primer | `60000A/01` | Flat, ready-mix white |
| 13 | Dulux Lifemaster Interior Primer | `59113/01` | Flat, white and pastel base |
| 14 | Dulux X-PERT Interior Primer | `11000/01` | Flat, white and pastel base |
| 15 | Dulux Ultra Classic Interior Primer | `36600/01` | Flat, white and pastel base |
| 16 | Dulux Ultra Classic Ceiling Paint | `7700/01` | Flat, white and pastel base |
| 17 | Dulux Lifemaster Interior Ceiling Paint | `59170/01` | Flat, white and pastel base |
| 18 | Dulux X-PERT Interior Ceiling Paint | `12170/01` | Flat, ready-mix white |

Raw PDFs are immutable source artifacts. Store extracted text, chunks, embeddings, and contextual summaries separately. Version the knowledge base, retain hashes and source URLs, and do not silently replace a TDS or SDS with a newer version. A monthly task already checks for manufacturer data-sheet updates.

---

## 3. Learning-first operating agreement

The owner wants to learn how to build projects like this independently. Treat explanation, inspection, experimentation, and reflection as deliverables—not as optional commentary.

For every meaningful feature or decision:

1. Explain the problem in plain language.
2. Explain the relevant concept and its place in the system.
3. Show the current implementation or evidence that motivates the change.
4. Present the smallest reasonable implementation.
5. Mention one or two alternatives and the trade-offs.
6. List the files expected to change before editing.
7. Implement a small vertical slice.
8. Run focused tests and show important results.
9. Walk through important functions and data flow.
10. Provide commands the owner can run independently.
11. Describe common failure modes and how to diagnose them.
12. Update the relevant learning, session, decision, and reference-mapping documents.
13. End with a recap and a small optional exercise or teach-back question.

Do not silently construct a large subsystem. When a milestone is too large for one understandable commit, split it.

### Expected teaching style

- Define new terms when first used.
- Tie abstractions to concrete coating examples.
- Prefer a small working example before introducing a framework abstraction.
- Make assumptions explicit.
- Separate manufacturer-supported facts from system inference.
- Do not hide failures with broad exceptions or silent fallbacks.
- Ask the owner before spending paid API credits.
- Ask before adding significant production dependencies.
- Ask before committing unless the owner has given standing permission for the current milestone.

---

## 4. Safety and domain behavior that the reference project does not supply

The reference repository is a generic transcript-question-answering RAG application. Coating Advisor is a decision-support system in a technical product domain. Its architecture must therefore add domain behavior that is absent from the reference project.

The system must eventually support:

- structured extraction of project facts such as interior/exterior, substrate, existing coating, exposure, wear, moisture, desired finish, damage, preparation condition, and application constraints;
- a clarification engine that asks for critical missing facts before making a recommendation;
- deterministic compatibility, exclusion, and escalation rules where known rules are safer than model improvisation;
- recommendations for complete systems—preparation, optional primer, and topcoat—not just a single similar product;
- one to three supported alternatives when the evidence does not justify one winner;
- safe abstention when the knowledge base does not support the project;
- source citations with document, page, section, and official URL;
- prominent limitations, contraindications, and safety guidance;
- comparison of traditional vector retrieval with metadata-aware, contextual, hybrid, and reranked retrieval;
- coating-specific metrics such as citation correctness, unsafe recommendation rate, missed-warning rate, clarification adequacy, system compatibility, and appropriate abstention;
- versioning of TDS/SDS sources and regression tests when documents change.

Do not let the reference application's generic architecture erase these requirements.

---

## 5. Reference repository

Reference: <https://github.com/Himanshu-1703/llmops-rag-app>

The owner wants to follow its high-level engineering journey and learn from its commit sequence. Treat it as a curriculum and comparison point.

### Important legal and engineering boundary

At the time of inspection, the reference repository's README said its license was **not yet specified**. Therefore:

- inspect ideas, architecture, sequencing, tests, commit intent, and trade-offs;
- do not copy source code, prompts, notebooks, data, reports, or generated artifacts into this project;
- implement original code based on the requirements of Coating Advisor;
- cite the reference repository in project notes where its architecture influenced a decision;
- verify the license again before any future direct code reuse.

### Reference repository's final stack

| Concern | Reference implementation |
|---|---|
| RAG orchestration | LangGraph and LangChain |
| Vector retrieval | Chroma and OpenAI embeddings |
| Evaluation | DeepEval, synthetic goldens, RAG metrics, custom `GEval` metrics |
| Experiment tracking | MLflow hosted with DagsHub |
| Prompt registry and runtime tracing | Langfuse |
| Guardrails | Guardrails AI plus custom and hub validators |
| API | FastAPI and Uvicorn |
| Frontend | Streamlit |
| Packaging | Docker and Docker Compose |
| CI/CD | GitHub Actions, AWS ECR/CodeDeploy/EC2-related deployment assets |

This list is descriptive, not a mandatory dependency list. Every dependency must solve a demonstrated Coating Advisor need.

---

## 6. How to follow the reference repository commit by commit

For each reference commit, Codex must perform this sequence before implementing anything:

1. **Inspect** the commit metadata and diff in the reference repository.
2. **Explain** the problem the commit attempted to solve.
3. **Identify** prerequisites and hidden assumptions.
4. **Evaluate** the quality of the implementation, including any generated artifacts or accidental noise.
5. **Classify** it using one of the five dispositions below.
6. **Design** an original Coating Advisor equivalent.
7. **Define** acceptance criteria and focused tests.
8. **Propose** the files that would change.
9. **Wait for agreement** when the decision or scope is material.
10. **Implement** one small increment.
11. **Verify** it locally.
12. **Document** the mapping, lesson, result, and next step.
13. **Recommend** an atomic commit message; make the commit only when authorized.

### Five dispositions

| Disposition | Meaning |
|---|---|
| **Reproduce** | The concept and sequence fit the project closely; implement an original equivalent now. |
| **Adapt** | The concept is valuable, but the implementation or domain assumptions must change. |
| **Combine** | Several small/noisy reference commits represent one coherent learning milestone here. |
| **Postpone** | The concept may be useful later but has unmet prerequisites or premature operational cost. |
| **Skip** | The commit contains no durable lesson for this project, is generated noise, or is unsuitable. |

### Definition of “follow commit by commit”

It does **not** mean matching every reference commit one-for-one. It means every reference commit is inspected and accounted for, while the owner's repository retains a clean, domain-appropriate history. CI test-run commits, report churn, cached tool state, local vector-store binaries, and arbitrary threshold nudges should usually be combined or skipped.

---

## 7. Full reference commit map

The inspected reference history contains 59 commits. The recommended initial disposition is a hypothesis; Codex should confirm it after inspecting each diff.

| # | Reference commit | Reference intent | Initial disposition | Coating Advisor lesson or equivalent |
|---:|---|---|---|---|
| 1 | `bbd76d5` | Created baseline RAG app | Adapt | Compare against the owner's completed baseline; document flow, dependencies, data path, citations, and known limitations. Do not rebuild automatically. |
| 2 | `8ba90aa` | Fixed typo in state | Skip/Combine | Apply a small fix only if an analogous defect exists; do not manufacture a matching commit. |
| 3 | `f0a6d33` | Created golden dataset | Adapt now | Define a coating-specific evaluation schema and create ten expert-reviewed scenarios before synthetic expansion. |
| 4 | `d62249a` | Tested retriever-specific metrics | Adapt | Add small retrieval metric experiments using known relevant documents/chunks. |
| 5 | `e09d1d1` | Tested RAG metrics on examples | Adapt | Smoke-test groundedness, answer relevance, citation support, and domain safety metrics on a few cases. |
| 6 | `a3fea37` | Evaluated complete dataset with custom metrics | Adapt | Run the frozen baseline across the reviewed coating benchmark and store machine-readable results. |
| 7 | `f8f3f42` | Changed paths and added project template | Adapt | Refactor only if current structure obstructs testing or repeatable runs. Preserve a green baseline. |
| 8 | `ab000a0` | Updated notebook paths | Combine | Include path fixes in the structural refactor; avoid a standalone noise commit. |
| 9 | `6061913` | Updated final evaluation pipeline | Adapt | Create a reproducible evaluation command with stable inputs, outputs, versions, and failure behavior. |
| 10 | `8edb85a` | Added MLflow tracking | Postpone until local eval works | Track params, code revision, KB version, prompt version, aggregate metrics, per-case artifacts, cost, and latency. |
| 11 | `c309234` | Re-evaluated with v2 prompt | Adapt | Change only the prompt, run the same benchmark, compare results, and document regressions as well as gains. |
| 12 | `96684a2` | Added `params.yaml` and Pydantic validation | Adapt | Introduce typed, validated experiment configuration only when multiple experimental settings exist. |
| 13 | `551a58f` | Created experimentation pipeline | Adapt | One command should load config, run cases, calculate metrics, save artifacts, and optionally log a run. |
| 14 | `bbc60dc` | Updated experimentation pipeline | Combine | Treat as hardening of the preceding milestone unless it contains a distinct design lesson. |
| 15 | `51cf8f2` | Test evaluation/tracking runs | Skip/Combine | Do not commit transient run noise; preserve useful fixtures and summaries only. |
| 16 | `160c11a` | Calculated regression thresholds | Adapt carefully | Derive provisional thresholds from evidence and error cost, not arbitrary round numbers. |
| 17 | `eaa46a5` | Finished threshold calculation | Combine | Complete the threshold milestone and record the method and uncertainty. |
| 18 | `66c4e69` | Regression and promotion testing | Adapt | Gate changes on critical safety/citation regressions and measured aggregate criteria. |
| 19 | `00e40cb` | Test run during session | Skip | Do not reproduce trial-run commits. |
| 20 | `02e1ffe` | Updated prompt-promotion criteria | Adapt | Refine champion/challenger rules only after inspecting real false positives and false negatives. |
| 21 | `17be35a` | Bias guardrail | Re-evaluate | Generic bias checks may not be the first safety priority. Prioritize unsupported product claims, incompatible systems, missing warnings, PII, and prompt injection. |
| 22 | `27bfa1f` | Component-wise guardrails | Adapt later | Validate input, retrieved evidence, structured decision, and final answer at appropriate boundaries. |
| 23 | `a75f199` | FastAPI routes | Adapt | Expose a stable typed API only after the core pipeline and evaluation interface are reasonably stable. |
| 24 | `2a7c82c` | Workflow changes | Inspect then adapt | Explain the trigger for the changes; avoid adding graph orchestration unless branching/state makes it useful. |
| 25 | `603c913` | Streamlit frontend | Postpone/adapt | Add a thin learning UI after the API contract works. The UI must show clarifications, systems, warnings, confidence, and citations. |
| 26 | `b138f78` | Improved latency | Adapt after measurement | Profile first. Cache or parallelize only demonstrated bottlenecks without weakening safety or evidence. |
| 27 | `2ade0ca` | Updated README | Reproduce continuously | Keep the README truthful after every milestone instead of postponing all documentation. |
| 28 | `16ec3ac` | Minor bug fixes | Combine | Include focused fixes with tests; avoid vague commit messages in this repository. |
| 29 | `de8770f` | Debug API router | Re-evaluate | Prefer observability and protected diagnostic endpoints. Never expose secrets, source documents, or internal state publicly. |
| 30 | `feaa453` | CI stage-promotion logic | Adapt later | Separate evaluation from promotion; require clear authorization and rollback behavior. |
| 31 | `482da7f` | CI pipeline v1 | Adapt | Begin with deterministic lint/unit tests; add expensive LLM evaluations as controlled jobs with budgets and secrets. |
| 32 | `2c3b56a` | Project restructure | Combine/adapt | Do not mimic structure. Refactor when the owner's tested architecture demonstrates a need. |
| 33 | `b97e55f` | CI test run 1 | Skip | Trial-run noise. |
| 34 | `115245b` | Added logger without CI trigger | Adapt | Add structured logging with redaction and trace identifiers; ensure path filters are intentional. |
| 35 | `c987527` | CI test run 2 | Skip | Trial-run noise. |
| 36 | `c0294ed` | CI test run 3 | Skip | Trial-run noise. |
| 37 | `e601fe6` | Updated metrics | Inspect/adapt | Record why a metric changed and rerun historical comparisons; never move goalposts silently. |
| 38 | `1f95f38` | Dummy vector-store change | Skip | Never create artificial production changes solely to trigger CI. Use explicit workflow dispatch or fixtures. |
| 39 | `388449d` | CI test run | Skip | Trial-run noise. |
| 40 | `e795baa` | CI test run | Skip | Trial-run noise. |
| 41 | `f1fe4ab` | CI test run | Skip | Trial-run noise. |
| 42 | `d3b9a2b` | CI test run | Skip | Trial-run noise. |
| 43 | `e9d4c97` | New CI run | Skip | Trial-run noise. |
| 44 | `76db7ee` | Docker and Compose | Adapt later | Containerize API/UI after local commands and persistence boundaries are stable. Keep raw PDFs and secrets outside images. |
| 45 | `ac9502b` | CI test run | Skip | Trial-run noise. |
| 46 | `ef2c3af` | Updated `.gitignore` | Reproduce as needed | Protect PDFs if redistribution is uncertain, local indexes, secrets, caches, run outputs, and large artifacts. |
| 47 | `b4a06e4` | CI test | Skip | Trial-run noise. |
| 48 | `d1276ad` | CI test run | Skip | Trial-run noise. |
| 49 | `24282e3` | CI test run 2 | Skip | Trial-run noise. |
| 50 | `642fa14` | CI test run 3 | Skip | Trial-run noise. |
| 51 | `e316bf7` | Created CD pipeline | Postpone | Choose a deployment target only after API/UI, storage, secrets, costs, and monitoring are defined. |
| 52 | `b01550c` | LLM-based PII and jailbreak guardrails | Adapt carefully | Compare deterministic and model-based checks. Measure latency, cost, false positives, and bypasses. |
| 53 | `4d0eb3e` | Updated CD versions | Combine | Pin and update deployment actions deliberately within the deployment milestone. |
| 54 | `5029680` | Manual AWS deployment | Postpone | Document manual deployment and rollback before automating, but do not assume AWS is the project's chosen platform. |
| 55 | `4eb6472` | Minor updates | Inspect/Combine | Require a specific description and tests for any equivalent changes. |
| 56 | `b92cb45` | Test CD run | Skip | Deployment trial noise. |
| 57 | `03eeab4` | Added CodeDeploy app spec and hooks | Postpone/Skip | Relevant only if CodeDeploy is deliberately selected. |
| 58 | `ae2e2dc` | Documented CodeDeploy steps | Postpone/Skip | Relevant only if CodeDeploy is deliberately selected. |
| 59 | `e31e879` | Enabled Langfuse tracing | Adapt later | Use Langfuse for runtime traces and prompt lifecycle after defining privacy, redaction, environments, and trace metadata. |

---

## 8. Recommended Coating Advisor milestone sequence

This sequence preserves the educational arc of the reference repository while inserting the domain-specific work it lacks.

| Our milestone | Suggested atomic commit message | Reference influence | Demonstrable outcome |
|---:|---|---|---|
| 0 | `docs: add reference-repository learning map` | Whole history | The project explicitly records what will be learned, adapted, postponed, or skipped. |
| 1 | `test: freeze baseline rag behavior` | `bbd76d5` | Baseline flow, configuration, sample behavior, and known limitations are reproducible. |
| 2 | `data: define coating evaluation case schema` | `f0a6d33` | A validated schema can represent project facts, expected questions, relevant sources, supported systems, warnings, and abstention. |
| 3 | `data: add ten expert-reviewed coating cases` | `f0a6d33` | Ten small, diverse, human-reviewed cases form the initial golden set. |
| 4 | `eval: add retrieval metric smoke tests` | `d62249a` | A few cases measure document/chunk retrieval and expose failures. |
| 5 | `eval: add groundedness and coating safety checks` | `e09d1d1` | Example-level generation, citation, warning, and abstention checks run repeatably. |
| 6 | `eval: benchmark the baseline rag pipeline` | `a3fea37` | The full reviewed benchmark produces versioned results and failure analysis. |
| 7 | `refactor: organize application and evaluation modules` | `f8f3f42`, `ab000a0` | Structure improves without changing measured behavior. |
| 8 | `eval: add reproducible evaluation command` | `6061913` | One documented command runs the same evaluation with stable inputs and outputs. |
| 9 | `config: validate experiment parameters` | `96684a2` | Config errors fail early and experiment settings are recorded. |
| 10 | `experiment: add tracked evaluation pipeline` | `8edb85a`, `551a58f` | Runs log KB, prompt, retrieval, model, cost, latency, code revision, and metrics. |
| 11 | `feat: extract structured coating requirements` | Domain addition | User descriptions become validated project facts with uncertainty preserved. |
| 12 | `feat: ask critical coating clarifications` | Domain addition | The system asks only questions whose answers can change safety or recommendation. |
| 13 | `eval: compare baseline and contextual retrieval` | Project goal | A controlled experiment changes only retrieval representation and compares outcomes. |
| 14 | `feat: add metadata-aware hybrid retrieval` | Domain addition | Product type, environment, substrate, document type, and lexical/vector evidence can be combined. |
| 15 | `feat: rerank coating evidence` | Domain addition | Reranking is justified by benchmark improvement, not by fashion. |
| 16 | `test: gate recommendation regressions` | `160c11a`–`02e1ffe` | Critical safety regressions block promotion; aggregate criteria are documented. |
| 17 | `feat: add coating-specific guardrails` | `17be35a`, `27bfa1f`, `b01550c` | Unsupported claims, incompatible systems, prompt attacks, and missing warnings are handled at appropriate boundaries. |
| 18 | `api: expose typed coating-advisor endpoints` | `a75f199` | A documented API returns clarifications or evidence-backed systems in a stable schema. |
| 19 | `ui: add coating project workflow` | `603c913` | A user can enter a project, answer clarifications, inspect systems, and open citations. |
| 20 | `ci: run deterministic quality checks` | `feaa453`, `482da7f` | Fast tests run on every change; expensive evaluations are controlled and budgeted. |
| 21 | `build: containerize the application` | `76db7ee` | Reproducible local runtime without embedding secrets, PDFs, or local vector databases. |
| 22 | `obs: trace rag runs with safe metadata` | `e31e879` | Runtime traces connect input, retrieval, prompt, model, output, latency, versions, and errors without leaking sensitive content. |
| 23 | `deploy: publish evaluated coating advisor` | CD commits | A documented, reversible deployment exists after the platform is deliberately chosen. |

The sequence is a roadmap, not a promise that every tool will be adopted. Evaluation evidence can change the plan.

---

## 9. Immediate next milestone

The next milestone should adapt reference commit `f0a6d33`: **create the first coating evaluation dataset**.

Do not begin by generating a large synthetic dataset. The owner has valuable paint-industry experience, and synthetic examples can amplify model assumptions. Begin with ten carefully reviewed cases that establish the expected behavior.

### Step 1: inspect before designing

Codex must first report:

- current repository root and Git status;
- current branch and recent commits;
- existing `AGENTS.md` and documentation;
- package/dependency manager and Python version;
- source tree and entry points;
- ingestion, chunking, embedding, retrieval, prompting, citation, and response flow;
- current test commands and results;
- where source manifests and derived artifacts live;
- whether an evaluation schema or dataset already exists;
- any unrelated user changes that must be preserved.

Do not edit code during this inspection.

### Step 2: compare the baseline with reference commit `bbd76d5`

Create or update `docs/reference-repo-map.md` with:

- what the reference baseline did;
- what the owner's baseline currently does;
- important differences;
- missing tests or reproducibility gaps;
- which differences are intentional domain improvements;
- whether a small baseline-freezing commit is needed before the dataset work.

### Step 3: propose the evaluation-case schema

The exact field names should fit the current codebase, but the schema should be capable of expressing:

```yaml
case_id: bathroom_existing_paint_001
title: Steamy bathroom with an existing coating
user_request: Plain-language customer request
project_facts:
  environment: interior
  area_type: bathroom
  substrate: drywall
  surface_state: previously_coated
  moisture_exposure: high_humidity
  desired_finish: eggshell
known_unknowns:
  - existing_coating_type
expected_clarifying_questions:
  - What type and condition is the existing coating?
critical_questions_before_recommendation:
  - existing_coating_type
expected_relevant_sources:
  - sku: 18010A/01
    document_type: TDS
    required_topics:
      - recommended_use
      - preparation
      - application
      - limitations
expected_supported_systems:
  - primer: conditional
    topcoat_skus:
      - 18010A/01
expected_warnings:
  - Address mildew or contamination before coating if present.
unsupported_or_excluded_products: []
expected_action: clarify_then_recommend
abstention_reason: null
review:
  status: approved
  reviewer: project_owner
  notes: Domain review notes
```

The schema should distinguish:

- facts explicitly stated by the user;
- facts inferred by the system;
- unknowns;
- questions that are merely useful;
- questions that are required before a safe recommendation;
- relevant source documents/chunks;
- acceptable systems rather than one rigid answer string;
- required warnings and limitations;
- supported alternatives;
- cases that should abstain or escalate.

### Step 4: draft ten human-reviewed scenarios

The first set should include diverse behavior, not ten easy product-look-up questions. Suggested coverage:

1. Ordinary interior repaint where no primer is necessarily required.
2. Steamy bathroom needing washability and moisture-aware guidance.
3. High-traffic hallway where scuff resistance matters.
4. Bare or repaired drywall requiring a suitable primer decision.
5. Previously coated trim where compatibility must be clarified before waterborne alkyd use.
6. Exterior siding project with weather/application limitations.
7. Exterior bare or weathered substrate requiring primer evidence.
8. Concrete or wood floor case within documented Floor Enamel scope.
9. Ceiling repaint case that should prefer an appropriate ceiling coating.
10. Unsupported, ambiguous, or high-risk project that should abstain or escalate.

The owner must review and correct the scenarios. Record corrections as domain knowledge, not merely as changes to expected strings.

### Step 5: add validation and tests

At minimum, test that:

- case identifiers are unique;
- required fields are present;
- referenced SKUs exist in the product manifest;
- referenced source documents exist in the knowledge-base manifest;
- action values are from a defined set;
- recommendation cases contain supported systems;
- abstention/escalation cases contain a reason;
- required warnings are represented structurally;
- the dataset can be loaded deterministically.

### Definition of done

- The schema is explained and validated.
- Ten cases exist and the owner has reviewed them.
- Dataset tests pass.
- No bulk synthetic generation has been introduced.
- `docs/reference-repo-map.md`, `docs/commit-plan.md`, `docs/learning-log.md`, and `docs/session-log.md` are updated.
- A proposed atomic commit is ready, with a clear diff summary and test evidence.

---

## 10. Required project tracking files

Codex should create missing tracking files only when the owner agrees and should update them as part of the same milestone that makes the corresponding decision.

### `docs/reference-repo-map.md`

Purpose: account for every reference commit and prevent blind copying.

Suggested columns:

| Reference commit | Concept | Important diff/decision | Disposition | Our equivalent | Status | Our commit | Evidence/lesson |
|---|---|---|---|---|---|---|---|

### `docs/commit-plan.md`

Purpose: keep the next few increments understandable and prevent scope drift.

Suggested entry:

```markdown
## Milestone: Human-reviewed evaluation cases

- Reference influence: `f0a6d33`
- Problem: We cannot measure whether RAG changes improve coating recommendations.
- Scope: schema, 10 reviewed cases, validation tests, documentation.
- Out of scope: synthetic generation, MLflow, CI gates, prompt changes.
- Files expected to change: ...
- Acceptance criteria: ...
- Test commands: ...
- Estimated API cost: none
- Status: proposed | agreed | in progress | verified | committed
- Proposed commit: `data: add ten expert-reviewed coating cases`
```

### `docs/learning-log.md`

Purpose: build the owner's transferable understanding.

Suggested entry:

```markdown
## YYYY-MM-DD — Golden evaluation datasets

### In my own words
The owner's explanation of the concept.

### What problem it solves
...

### How it appears in this repository
...

### Alternatives and trade-offs
...

### Common failure mode
...

### Commands I can run
...

### Exercise / teach-back
...
```

### `docs/session-log.md`

Purpose: allow a later Codex session to resume without depending on chat memory.

Suggested entry:

```markdown
## YYYY-MM-DD

- Goal:
- Starting Git state:
- Files inspected:
- Decisions made:
- Files changed:
- Tests and results:
- Open questions:
- Risks/debt:
- Suggested next step:
- Last verified commit:
```

### `docs/decisions/`

Purpose: preserve decisions that would otherwise be re-litigated.

Use lightweight Architecture Decision Records only for material decisions. Example:

```markdown
# ADR-0003: Use system-level answers in evaluation cases

- Status: Accepted
- Date: YYYY-MM-DD

## Context
The assistant recommends preparation, optional primer, and topcoat. A single expected product label cannot represent valid alternatives.

## Decision
Represent one or more acceptable coating systems structurally and score required components and exclusions.

## Alternatives considered
- Exact answer string
- Single expected SKU

## Consequences
Evaluation logic is more complex but better matches the product behavior.
```

Do not generate empty ADRs for choices that have not been made.

---

## 11. Experiment and tool ownership

If these tools are adopted, keep their responsibilities distinct:

| Tool/category | Intended responsibility |
|---|---|
| Unit/integration tests | Deterministic code behavior, schemas, rules, manifests, parsing, and API contracts |
| DeepEval or selected evaluation framework | Offline retrieval/generation metrics and LLM-as-judge experiments where justified |
| MLflow | Experiment parameters, artifacts, metrics, versions, comparisons, and champion/challenger records |
| Langfuse | Runtime traces, prompt registry/lifecycle, operational latency/error analysis |
| Git | Source code, configuration, dataset definitions where permitted, decisions, and reviewable history |

Do not add overlapping tools without a clear reason. Do not let an external platform become the only location of critical results; retain reproducible local artifacts or summaries.

Every experiment should record at least:

- Git revision;
- knowledge-base version and document hashes;
- dataset version;
- prompt version;
- model and embedding model;
- chunking and retrieval settings;
- filters, fusion, and reranking settings;
- random seed when applicable;
- per-case and aggregate metrics;
- latency and estimated cost;
- failures and skipped cases;
- environment name;
- timestamp.

Change one major variable at a time when the goal is causal comparison.

---

## 12. Git and commit discipline

- Inspect `git status` before editing.
- Preserve unrelated user changes.
- Never reset, discard, or overwrite user work without explicit approval.
- Keep raw TDS/SDS PDFs, secrets, local vector-store binaries, tool caches, and large generated reports out of public Git history unless a deliberate policy says otherwise.
- Use specific commit messages that describe behavior, not vague messages such as “minor updates,” “test run,” or “changes.”
- A commit should represent one understandable lesson or behavior change.
- Tests and documentation that prove/explain the behavior belong in the same commit when practical.
- Avoid commits that contain only transient experiment output or CI retries.
- Before committing, show the owner:
  - the diff summary;
  - test evidence;
  - documentation updates;
  - known limitations;
  - proposed commit message.

Suggested commit-body structure:

```text
Problem:
- ...

Change:
- ...

Verification:
- ...

Learning:
- ...

Reference influence:
- Himanshu-1703/llmops-rag-app@f0a6d33 (concept only; original implementation)
```

---

## 13. Session-start checklist for Codex

At the start of each session:

1. Read the active `AGENTS.md` files.
2. Read this handoff and the master project brief.
3. Read the latest entries in the session log, learning log, commit plan, and relevant ADRs.
4. Run `git status --short --branch` and inspect recent history.
5. Identify the current milestone and its acceptance criteria.
6. Inspect relevant code and tests before proposing changes.
7. Run the smallest safe baseline verification.
8. Summarize what is known, what is uncertain, and what you recommend next.
9. Do not edit until the requested task and scope are clear.

At the end of each session:

1. Run focused tests and any agreed broader checks.
2. Summarize changed files and behavior.
3. Update the tracking documents.
4. Record incomplete work and exact next steps.
5. Explain the main concept learned.
6. Offer one small exercise or teach-back question.
7. Show the proposed commit and wait for authorization if required.

---

## 14. Exact opening prompt for a new Codex session

Copy and paste the following after placing the documents in the repository:

```text
Work as my technical mentor and implementation partner on the Coating Advisor learning project.

First read all active AGENTS.md files and then read these documents completely:
- docs/Coating_Compass_Project_Brief.md
- docs/Coating_Advisor_Reference_Repo_Codex_Handoff.md
- docs/reference-repo-map.md, if it exists
- docs/commit-plan.md, if it exists
- docs/learning-log.md, if it exists
- docs/session-log.md, if it exists
- relevant files in docs/decisions/, if they exist

Then inspect the repository without modifying anything:
- show the repository root, branch, Git status, and recent commits;
- identify existing user changes and preserve them;
- inspect the README, dependency files, source tree, tests, data manifests, configuration, and current RAG entry points;
- trace ingestion -> chunking -> embedding/indexing -> retrieval -> prompt -> generation -> citations/output;
- run or propose the smallest safe baseline verification;
- identify what evaluation assets already exist.

The basic RAG implementation is complete. Do not rebuild it automatically. We are using https://github.com/Himanshu-1703/llmops-rag-app as a high-level learning reference, not as source code to copy. Its license was unspecified when reviewed, so inspect concepts and commits but write original code.

Our immediate target is to adapt reference commit f0a6d33: define a coating-specific evaluation-case schema and create ten carefully reviewed coating scenarios before synthetic expansion. First compare our current baseline with reference commit bbd76d5 and explain any foundation gaps.

For this turn, do not implement. Return:
1. your understanding of the product and learning contract;
2. a concise map of the current implementation;
3. gaps or risks that affect the evaluation-dataset milestone;
4. the proposed schema and why each field exists;
5. the exact files you would create or change;
6. acceptance criteria and test commands;
7. questions that materially require my domain judgment;
8. a proposed small commit sequence.

Keep the project learning-first: explain concepts and trade-offs, make assumptions explicit, change one major experimental variable at a time, update the tracking files, and do not commit, spend paid API credits, add major dependencies, push, or deploy without my approval.
```

---

## 15. How to transfer this conversation to Codex reliably

The most reliable method is to transfer the durable facts and instructions as versioned repository files. Do not depend on one chat session's memory.

### Recommended method

1. Download these two documents:
   - `Coating_Compass_Project_Brief.md`
   - `Coating_Advisor_Reference_Repo_Codex_Handoff.md`
2. Place them in your repository:
   - `docs/Coating_Compass_Project_Brief.md`
   - `docs/Coating_Advisor_Reference_Repo_Codex_Handoff.md`
3. Create a concise root `AGENTS.md` using the companion template.
4. Commit these context files so every clone and later session can use the same instructions.
5. Open Codex from the repository root.
6. Paste the exact opening prompt from the previous section.
7. Confirm that Codex reports the correct repository root and lists the instruction files it read.
8. Review its summary before allowing implementation.

### Why use both `AGENTS.md` and detailed docs?

- `AGENTS.md` is the concise, automatically discovered operating contract.
- The detailed documents contain the larger product context, data catalog, roadmap, reference history, and teaching workflow.
- Keeping the auto-loaded instructions short reduces truncation and makes the highest-priority rules easy to find.
- Explicitly naming the detailed docs in the opening prompt ensures they are read for the task.

### Sharing the chat itself

ChatGPT's **Share** option can create a link containing conversation history or an individual response, depending on the available sharing controls. Review the shared preview carefully because uploaded files and sensitive text may be included. A personal-account shared link is generally a snapshot, while managed-workspace access can be restricted by workspace rules.

However, a shared chat link should be treated as a convenience for human review, not as the project's durable instruction system. A new Codex session should be given repository files and an explicit opening prompt even if a shared-chat link also exists.

### Privacy check before sharing

Before creating any shared link:

- remove passwords, API keys, tokens, private customer information, proprietary employer material, and private repository details;
- review whether uploaded files are included;
- confirm the intended audience and workspace restrictions;
- remember that anyone allowed to open a link may be able to forward its contents;
- delete the shared link when it is no longer needed.

---

## 16. Root `AGENTS.md` design guidance

The root `AGENTS.md` should contain rules that apply to nearly every task. Avoid putting the entire product brief inside it.

It should tell Codex to:

- read the two detailed documents before substantial work;
- preserve user changes and inspect Git state;
- operate as a learning mentor;
- explain before making meaningful edits;
- implement small tested increments;
- maintain the tracking files;
- use manufacturer evidence for coating claims;
- keep raw documents immutable;
- distinguish fact, inference, uncertainty, and abstention;
- avoid paid calls, new major dependencies, commits, pushes, and deployment without approval;
- respect current project commands and conventions discovered from the repository.

Do not place secrets, temporary goals, or long session transcripts in `AGENTS.md`.

---

## 17. Non-goals and anti-patterns

Do not:

- rebuild a working baseline solely to resemble the reference repository;
- copy unlicensed source code;
- add LangGraph only because the reference uses it;
- add MLflow, Langfuse, DeepEval, Guardrails AI, Streamlit, Docker, AWS, or any other tool before the problem and acceptance criteria are clear;
- generate hundreds of synthetic cases before establishing a reviewed seed set;
- use exact-answer string matching as the only evaluation of a valid coating system;
- optimize aggregate scores while allowing unsafe recommendations or missed critical warnings;
- change prompt, model, chunks, embeddings, filters, reranker, and dataset simultaneously;
- silently replace data sheets or rebuild the index without recording a knowledge-base version;
- commit raw API outputs, tool caches, local vector databases, giant reports, or transient run artifacts;
- expose a debug route containing secrets, raw source documents, internal prompts, or sensitive traces;
- represent the project as manufacturer-approved;
- use private customer or employer data;
- let chat history become the only record of a decision.

---

## 18. What success looks like

At any point, the owner should be able to answer:

- What problem does the current milestone solve?
- What did the reference repository teach us?
- What did we change for the coating domain?
- What evidence shows the change helped?
- What trade-off did we accept?
- What files and commands implement it?
- What could fail and how would we diagnose it?
- Which source documents support a recommendation?
- When should the system clarify, abstain, or escalate?
- What is the next smallest useful step?

The finished portfolio story should be earned through the repository history: a basic RAG baseline, a reviewed coating benchmark, controlled retrieval experiments, structured recommendation behavior, domain safety metrics, reproducible experiments, regression gates, a typed API and useful UI, responsible observability, and a deliberately chosen deployment path.

The goal is not merely a working demo. The goal is a system the owner understands deeply enough to rebuild, defend, test, and extend without relying on hidden work.

## Framework-first rule (2026-10-03)

Prefer maintained LangChain and LangGraph components over handwritten infrastructure
when they satisfy safety and evidence requirements. Retain coating validation,
original-only evidence boundaries, deterministic safety rules, and behavior the
frameworks cannot supply. Choose the least code the owner can clearly explain.
See decision 0002 for the repository-wide review.
