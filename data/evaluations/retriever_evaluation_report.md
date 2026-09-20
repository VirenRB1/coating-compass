# Retriever Evaluation Results

Generated from completed DeepEval result artifacts. Scores use a 0–1 scale.

## Baseline — 20260920T161703Z

- Collection: `coating-compass-baseline-v1`
- Retrieval K: `5`
- Embedding model: `text-embedding-3-small`
- Evaluation model: `gpt-5-mini-2025-08-07`
- Golden dataset SHA-256: `f9e69b3021fb5eea624287a46c661cf64cdd9b77b9f68e2deaff65af17944412`

| Metric | Average | Passed |
|---|---:|---:|
| Contextual Recall | 0.594 | 15/20 |
| Contextual Precision | 0.944 | 20/20 |
| Contextual Relevancy | 0.602 | 15/20 |

| Case | Recall | Precision | Relevancy |
|---|---:|---:|---:|
| manual_001 | 0.600 | 1.000 | 0.457 |
| manual_002 | 0.625 | 0.887 | 0.560 |
| manual_003 | 0.571 | 0.887 | 0.552 |
| manual_004 | 0.833 | 0.804 | 0.620 |
| manual_005 | 0.733 | 1.000 | 0.781 |
| manual_006 | 0.455 | 1.000 | 0.609 |
| manual_007 | 1.000 | 1.000 | 0.825 |
| manual_008 | 0.875 | 1.000 | 0.609 |
| manual_009 | 0.750 | 1.000 | 0.714 |
| manual_010 | 1.000 | 1.000 | 0.509 |
| manual_011 | 0.714 | 1.000 | 0.903 |
| manual_012 | 0.000 | 0.679 | 0.644 |
| manual_013 | 0.000 | 0.867 | 0.660 |
| manual_014 | 0.333 | 0.887 | 0.409 |
| manual_015 | 0.600 | 1.000 | 0.368 |
| manual_016 | 0.500 | 1.000 | 0.500 |
| manual_017 | 0.500 | 0.867 | 0.325 |
| manual_018 | 1.000 | 1.000 | 0.347 |
| manual_019 | 0.200 | 1.000 | 0.737 |
| manual_020 | 0.588 | 1.000 | 0.902 |

## Architecture Comparison

| Architecture | Recall | Precision | Relevancy | Cases |
|---|---:|---:|---:|---:|
| baseline | 0.594 | 0.944 | 0.602 | 20 |
