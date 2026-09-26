# Generator Evaluation Results

Generated from completed DeepEval result artifacts. Scores use a 0-1 scale.

## Baseline - 20260920T165827Z

- Collection: `coating-compass-baseline-v1`
- Retrieval K: `5`
- Generator model: `openai/gpt-oss-20b`
- Judge model: `gpt-5-mini-2025-08-07`
- Golden dataset SHA-256: `f9e69b3021fb5eea624287a46c661cf64cdd9b77b9f68e2deaff65af17944412`

| Metric | Average | Passed |
|---|---:|---:|
| Answer Relevancy | 0.584 | 12/20 |
| Faithfulness | 0.580 | 12/20 |

| Case | Answer Relevancy | Faithfulness |
|---|---:|---:|
| manual_001 | 1.000 | 0.900 |
| manual_002 | 1.000 | 1.000 |
| manual_003 | 1.000 | 1.000 |
| manual_004 | 1.000 | 1.000 |
| manual_005 | 0.000 | 0.000 |
| manual_006 | 0.000 | 0.000 |
| manual_007 | 1.000 | 0.952 |
| manual_008 | 0.800 | 1.000 |
| manual_009 | 1.000 | 1.000 |
| manual_010 | 1.000 | 0.750 |
| manual_011 | 0.000 | 0.000 |
| manual_012 | 0.000 | 0.000 |
| manual_013 | 0.000 | 0.000 |
| manual_014 | 0.000 | 0.000 |
| manual_015 | 1.000 | 1.000 |
| manual_016 | 0.000 | 0.000 |
| manual_017 | 1.000 | 1.000 |
| manual_018 | 0.875 | 1.000 |
| manual_019 | 0.000 | 0.000 |
| manual_020 | 1.000 | 1.000 |

## Architecture Comparison

| Architecture | Answer Relevancy | Faithfulness | Cases |
|---|---:|---:|---:|
| baseline | 0.584 | 0.580 | 20 |
