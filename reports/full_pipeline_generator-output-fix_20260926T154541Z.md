# Full Pipeline Evaluation

DeepEval scores use a 0-1 scale. GEval scores are model judgments and must be reviewed alongside their reasons and coating-domain checks.

## Run metadata

- Label: `generator-output-fix`
- Timestamp (UTC): `20260926T154541Z`
- Status: `complete`
- Collection: `coating-compass-baseline-v1`
- Retrieval K: `5`
- Embedding model: `text-embedding-3-small`
- Generator model: `openai/gpt-oss-20b`
- Generator max tokens: `2000`
- Generator reasoning effort: `low`
- Judge model: `gpt-5-mini-2025-08-07`
- Parallel case workers: `1`
- Per-metric timeout: `300 seconds`
- Golden dataset SHA-256: `f9e69b3021fb5eea624287a46c661cf64cdd9b77b9f68e2deaff65af17944412`

## Aggregate results

| Metric | Average | Passed |
|---|---:|---:|
| Contextual Recall | 0.375 | 0/1 |
| Contextual Precision | 0.887 | 1/1 |
| Contextual Relevancy | 0.625 | 1/1 |
| Answer Relevancy | 1.000 | 1/1 |
| Faithfulness | 1.000 | 1/1 |
| Answer Simplicity | 0.900 | 1/1 |
| Answer Correctness | 0.700 | 1/1 |

## Per-case results

| Case | Contextual Recall | Contextual Precision | Contextual Relevancy | Answer Relevancy | Faithfulness | Answer Simplicity | Answer Correctness |
|---|---:|---:|---:|---:|---:|---:|---:|
| manual_002 | 0.375 | 0.887 | 0.625 | 1.000 | 1.000 | 0.900 | 0.700 |

## Judge reasons

### manual_002

**Question:** I want to paint my interior cabinets and some furniture. Recommend me a suitable paint for this task. I would like a paint that is really durable and easy to clean and also has self-leveling properties.

- **Contextual Recall (0.375):** The score is 0.38 because node(s) in retrieval context only partially back the expected output: sentence 2’s claims about durability, flow/leveling and water clean-up are supported by nodes 5, 2 and 1; sentence 5’s recommendation for primer + two topcoats (and primer 23010) is reflected in node 4; sentence 8 (clean tools with water) aligns with node 1. However, several key items are missing or conflict with the nodes: sentence 1 and part of sentence 5 name Dulux X‑pert 22010 but no node mentions that product; sentence 3’s explicit “furniture, cabinets” phrasing is not in the nodes (node 1 lists walls/ceilings/doors/trim only); sentence 4’s quoted surface‑prep text is not present in any node; sentence 6’s 10–30°C range conflicts with node 4 (which gives 10–32°C); and sentence 7’s drying/cleaning intervals differ substantially from times shown in node 5.
- **Contextual Precision (0.887):** The score is 0.89 because the top-ranked contexts (first and second nodes) directly match the request, calling out "Dries quickly", "Clean-up with water", "Good Scrubbability - Withstands repeated cleaning." and "Good flow & levelling", and the fourth and fifth nodes further support primer/topcoat guidance ("Two topcoats are recommended", "Dulux X-PERT® Waterborne Alkyd Primer/Sealer 23010") and "Exceptional flow and leveling: Results in a smooth and flawless finish" with "exceptional durability, scrub and burnish resistance." It is not higher because the third node—focused on exterior surfaces like "Concrete, stucco or masonry" and products such as "Dulux Weatherguard1530"—is less relevant to interior cabinets/furniture yet is ranked above the more relevant fourth and fifth nodes, reducing precision.
- **Contextual Relevancy (0.625):** The score is 0.62 because the retrieval context contains several directly relevant product claims—e.g., "Good Scrubbability - Withstands repeated cleaning", "Excellent flow & levelling", "Exceptional flow and leveling", "100% Acrylic Latex Paint", and "Self-priming paint with excellent adhesion"—which align with durability, cleanability and self-leveling. However, many retrieved items are off‑topic (reducing overall relevance), for example "a eggshell finish is desired.", "Not formulated to be used on floors.", "0 g/L VOC", "Spray equipment must be handled with due care", and "Concrete, stucco or masonry cured for at least 30 days".
- **Answer Relevancy (1.000):** The score is 1.00 because the assistant's output contained no irrelevant statements and directly addressed durable, easy-to-clean, self-leveling paint options for cabinets and furniture. It cannot be higher because 1.00 is the maximum score.
- **Faithfulness (1.000):** The score is 1.00 because the contradictions list is empty, indicating the actual output fully aligns with the retrieval context and no inconsistencies were found — great job keeping it faithful!
- **Answer Simplicity (0.900):** The response directly addresses the user’s requirements (durability, easy cleaning, self‑leveling) by recommending two Dulux water‑based acrylic products and clearly explains why each fits (scrubbability, burnish resistance, flow & levelling). It is well organized (table, limitations, application notes) and gives actionable safety/usage guidance (surface prep, temperature/humidity range, two coats, and explicit exclusions for floors/prolonged water). Minor shortcomings: a couple of technical terms (e.g., “burnish resistance”) aren’t explained for a non‑specialist and drying times/primer brand specifics are omitted, but overall it is complete and cites TDS sources for verification.
- **Answer Correctness (0.700):** Strengths: The response recommends two Dulux products (Ultra 949000 and Diamond 151100) that are supported by the retrieved TDSs and explicitly address the user’s requirements (durability, scrubbability/cleanability, and flow/leveling). It correctly lists application limits (not for prolonged water contact or floors), sensible surface-prep advice (clean, dry, sand; primer may be needed), temperature/humidity ranges (10–32°C) and the two‑coat recommendation tied to the Kitchen & Bath TDS. Shortcomings: it does not follow the expected recommendation of Dulux X‑pert Waterborne Alkyd 22010 (the TDS for that product was the expected choice), it asserts suitability for cabinets/furniture without clear TDS language for those specific uses (Ultra is targeted to walls/ceilings), and it omits key manufacturer details present in the retrieval (specific primer system recommendations such as X‑pert 23010 and explicit drying/“before cleaning” wait times). These omissions and the unsupported extension to furniture/cabinets justify a partial deduction.
