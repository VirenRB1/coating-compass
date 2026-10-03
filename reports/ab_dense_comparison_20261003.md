# Controlled baseline vs contextual dense comparison

A uses baseline dense retrieval; B uses contextual dense retrieval.

Both runs completed: 20 questions per mode, seven metrics per question (280 scores), in 16.8 minutes including source validation and judging.

## Controls and execution

- Generator: Groq-hosted `openai/gpt-oss-20b`, temperature 0, 2,000 output tokens, low reasoning effort.
- Judge: `gpt-5-mini-2025-08-07`; embeddings: `text-embedding-3-small`; K=5.
- Shared prompt version: 1; SHA-256: `cd2eb717bbee8b7683b84151564efc4f75a5b9c4ab71b524681b7f11c10713e1`.
- Golden dataset SHA-256: `f9e69b3021fb5eea624287a46c661cf64cdd9b77b9f68e2deaff65af17944412`.
- Existing 921-chunk collections reused; original manufacturer text alone supplies answer/judge evidence.
- Forty case workers, seven native async metric calls per ready answer, one shared LangChain generator limiter at three requests/minute.
- Request pacing is an estimate; it is not an exact token limiter. Successful answers and individual metrics are checkpointed.
- Recovery: eight first-pass case jobs (four per mode) encountered Windows Proactor I/O/loop errors. HTTP judging was switched to Python's native SelectorEventLoop on Windows. The same artifacts resumed successfully, reusing all answers and successful scores; `run.previous_attempts` retains the original failures.

## Aggregate results

| Metric | A mean | B mean | B minus A | A passed | B passed |
|---|---:|---:|---:|---:|---:|
| Contextual Recall | 0.628 | 0.601 | -0.027 | 14/20 | 16/20 |
| Contextual Precision | 0.918 | 0.981 | +0.063 | 20/20 | 20/20 |
| Contextual Relevancy | 0.617 | 0.627 | +0.010 | 15/20 | 14/20 |
| Answer Relevancy | 0.968 | 0.984 | +0.016 | 20/20 | 20/20 |
| Faithfulness | 0.951 | 0.973 | +0.022 | 20/20 | 20/20 |
| Answer Simplicity | 0.845 | 0.855 | +0.010 | 20/20 | 20/20 |
| Answer Correctness | 0.625 | 0.645 | +0.020 | 15/20 | 15/20 |

B scores higher on six of seven averages, especially precision (+0.063), while
recall decreases (-0.027). Correctness gains only 0.020 and both modes pass 15/20
correctness cases. This is a modest, mixed result rather than a clear overall win.

## Paired outcomes

| Metric | B higher | Equal | B lower |
|---|---:|---:|---:|
| Contextual Recall | 9 | 4 | 7 |
| Contextual Precision | 6 | 12 | 2 |
| Contextual Relevancy | 12 | 0 | 8 |
| Answer Relevancy | 6 | 11 | 3 |
| Faithfulness | 6 | 10 | 4 |
| Answer Simplicity | 8 | 5 | 7 |
| Answer Correctness | 9 | 5 | 6 |

## Case-level correctness and faithfulness

| Case | A correctness | B correctness | A faithfulness | B faithfulness |
|---|---:|---:|---:|---:|
| manual_001 | 0.800 | 0.400 | 0.875 | 1.000 |
| manual_002 | 0.300 | 0.500 | 0.960 | 1.000 |
| manual_003 | 0.700 | 0.400 | 1.000 | 0.929 |
| manual_004 | 0.700 | 0.700 | 1.000 | 1.000 |
| manual_005 | 0.600 | 0.800 | 1.000 | 0.882 |
| manual_006 | 0.200 | 0.200 | 0.800 | 0.950 |
| manual_007 | 0.800 | 0.700 | 1.000 | 1.000 |
| manual_008 | 0.400 | 0.600 | 0.909 | 1.000 |
| manual_009 | 0.700 | 0.900 | 1.000 | 1.000 |
| manual_010 | 0.700 | 0.800 | 0.643 | 0.917 |
| manual_011 | 0.600 | 0.800 | 1.000 | 1.000 |
| manual_012 | 0.300 | 0.200 | 0.970 | 0.946 |
| manual_013 | 0.300 | 0.800 | 1.000 | 1.000 |
| manual_014 | 0.900 | 0.900 | 1.000 | 1.000 |
| manual_015 | 0.700 | 0.300 | 0.929 | 0.846 |
| manual_016 | 0.700 | 0.700 | 1.000 | 1.000 |
| manual_017 | 0.600 | 0.700 | 1.000 | 1.000 |
| manual_018 | 1.000 | 1.000 | 1.000 | 1.000 |
| manual_019 | 0.600 | 0.800 | 0.941 | 1.000 |
| manual_020 | 0.900 | 0.700 | 1.000 | 1.000 |

## Limits and interpretation

Empty answers: A 0/20; B 0/20. Both final reports have all seven metrics for every
case and no unresolved failed jobs. Eight first-pass jobs required the recorded
Windows event-loop recovery above.

Case review matters: manual_013 correctness improves from 0.3 to 0.8, with B
qualifying the deck/floor use. Manual_015 regresses from 0.7 to 0.3; the judge
flags permission to apply some water-based topcoats directly over alkyd against
retrieved primer guidance. Both modes score 0.2 on manual_006, where product
selection, preparation, and warning omissions persist. The full reports retain
all judge reasons so these claims can be checked against the original evidence.

Higher is better for these scores. The measurements distinguish retrieval quality from answer quality; do not combine them into a single unvalidated promotion score. Review individual reasons and unsupported claims before choosing retrieval defaults.

This is one 20-question paired experiment with LLM judges, not a statistical significance claim or proof of coating safety. Judge scores can vary between runs. No hybrid BM25 experiment is included. Deterministic coating compatibility, warnings, citations, and abstention checks remain needed.

## Artifacts

- [A baseline dense full report](full_pipeline_ab-20261003-parallel-full-A_20261003T195245Z.md); machine-readable artifact: `full_pipeline_ab-20261003-parallel-full-A_20261003T195245Z.json`.
- [B contextual dense full report](full_pipeline_ab-20261003-parallel-full-B_20261003T195245Z.md); machine-readable artifact: `full_pipeline_ab-20261003-parallel-full-B_20261003T195245Z.json`.
