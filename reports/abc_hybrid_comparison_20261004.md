# Baseline, contextual dense, and contextual hybrid comparison

A/B are the completed 2026-10-03 dense runs; C is the 2026-10-04 contextual hybrid run.

All runs contain the same 20 reviewed questions and seven metrics per question.
Generator, judge, embedding model, prompt name/label/version, dataset hash, and final K match.
This is a historical comparison with separate model calls, not a fresh simultaneous three-way experiment. LLM judgments and answers can vary between runs.

C uses maintained LangChain EnsembleRetriever weighted reciprocal rank fusion: dense K=5, contextual BM25 K=5, equal weights, c=60, final K=5, stable chunk-ID deduplication.
Existing contextual vectors are reused and only original manufacturer text supplies answer/judge evidence.

C validated parameters SHA-256: `c93715de09b1d41ea4568a362f0cc5e40aaa2db1ea3069139d23853f6e650399`.
Golden dataset SHA-256: `f9e69b3021fb5eea624287a46c661cf64cdd9b77b9f68e2deaff65af17944412`.

## Aggregate results

| Metric | A baseline | B contextual dense | C hybrid | C minus A | C minus B | C passed |
|---|---:|---:|---:|---:|---:|---:|
| Contextual Recall | 0.628 | 0.601 | 0.663 | +0.035 | +0.062 | 18/20 |
| Contextual Precision | 0.918 | 0.981 | 0.963 | +0.045 | -0.018 | 20/20 |
| Contextual Relevancy | 0.617 | 0.627 | 0.591 | -0.026 | -0.036 | 15/20 |
| Answer Relevancy | 0.968 | 0.984 | 0.958 | -0.010 | -0.026 | 20/20 |
| Faithfulness | 0.951 | 0.973 | 0.988 | +0.036 | +0.014 | 20/20 |
| Answer Simplicity | 0.845 | 0.855 | 0.875 | +0.030 | +0.020 | 20/20 |
| Answer Correctness | 0.625 | 0.645 | 0.710 | +0.085 | +0.065 | 19/20 |

## Case-level correctness and faithfulness

| Case | A correctness | B correctness | C correctness | B faithfulness | C faithfulness |
|---|---:|---:|---:|---:|---:|
| manual_001 | 0.800 | 0.400 | 0.500 | 1.000 | 1.000 |
| manual_002 | 0.300 | 0.500 | 0.700 | 1.000 | 1.000 |
| manual_003 | 0.700 | 0.400 | 0.700 | 0.929 | 1.000 |
| manual_004 | 0.700 | 0.700 | 0.800 | 1.000 | 1.000 |
| manual_005 | 0.600 | 0.800 | 0.800 | 0.882 | 1.000 |
| manual_006 | 0.200 | 0.200 | 0.600 | 0.950 | 1.000 |
| manual_007 | 0.800 | 0.700 | 0.700 | 1.000 | 1.000 |
| manual_008 | 0.400 | 0.600 | 0.700 | 1.000 | 1.000 |
| manual_009 | 0.700 | 0.900 | 0.600 | 1.000 | 0.833 |
| manual_010 | 0.700 | 0.800 | 0.600 | 0.917 | 1.000 |
| manual_011 | 0.600 | 0.800 | 0.700 | 1.000 | 0.917 |
| manual_012 | 0.300 | 0.200 | 0.400 | 0.946 | 1.000 |
| manual_013 | 0.300 | 0.800 | 1.000 | 1.000 | 1.000 |
| manual_014 | 0.900 | 0.900 | 0.800 | 1.000 | 1.000 |
| manual_015 | 0.700 | 0.300 | 0.700 | 0.846 | 1.000 |
| manual_016 | 0.700 | 0.700 | 0.700 | 1.000 | 1.000 |
| manual_017 | 0.600 | 0.700 | 0.700 | 1.000 | 1.000 |
| manual_018 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| manual_019 | 0.600 | 0.800 | 0.700 | 1.000 | 1.000 |
| manual_020 | 0.900 | 0.700 | 0.800 | 1.000 | 1.000 |

## Validation and limits

C: 20 cases, 140 finite scores, 0 empty answers. First pass took 8.3 minutes and completed 139/140 judgments.
Total wall span was 59.4 minutes, including the interval before single-metric recovery; this is not uninterrupted execution latency.
One manual_020 contextual relevancy judgment timed out after 300 seconds. Resume reused all 20 answers and 139 successful metric dictionaries unchanged, retried only that judgment, and retained failed-attempt history.
The live log also retains httpx2 async-client cleanup warnings (Event loop is closed); final cases have no metric errors or pending failures. Client lifecycle cleanup remains a follow-up issue.
DeepEval-reported successful judge cost for C: USD 1.4480; excludes smoke, the timed-out attempt's unrecorded usage, generation, and embeddings, and is not a provider billing statement.
RAG scores do not establish coating safety. Inspect unsupported claims, required warnings, citations, abstention, and individual regressions before changing defaults. The app remains in auto mode.

## Artifacts

- Case review: manual_009 correctness fell 0.300 versus B; the judge flags an incorrect exterior application temperature and omitted timing qualifications.
- Case review: manual_010 correctness fell 0.200 versus B; the judge flags omitted SDS safety qualifications. Do not promote hybrid based on aggregate correctness alone.

- [A baseline dense](full_pipeline_ab-20261003-parallel-full-A_20261003T195245Z.md); local JSON: `full_pipeline_ab-20261003-parallel-full-A_20261003T195245Z.json`.
- [B contextual dense](full_pipeline_ab-20261003-parallel-full-B_20261003T195245Z.md); local JSON: `full_pipeline_ab-20261003-parallel-full-B_20261003T195245Z.json`.
- [C contextual hybrid](full_pipeline_hybrid-20261004-full_20261004T164938Z.md); local JSON: `full_pipeline_hybrid-20261004-full_20261004T164938Z.json`.
