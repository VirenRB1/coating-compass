# Learning log

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
