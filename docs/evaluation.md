# How terminology recognition is evaluated

## Task

Given a user's health question, identify every medical concept it mentions and map each one to a canonical concept id (for example, "Advil" → `ibuprofen`, "HTN" → `hypertension`). For each concept, also decide whether the user said they have it or said they don't (negation).

## Data

Each line of a `.jsonl` file is one question:

```json
{"id": "q005",
 "text": "I have a cough and sore throat but no fever. Should I see a doctor?",
 "expected": ["cough", "sore_throat", "fever"],
 "negated": ["fever"],
 "out_of_lexicon": [],
 "tags": ["negation", "symptom"]}
```

- `expected`: concept ids a human annotator would mark (every one must exist in the lexicon).
- `negated`: the subset the user said they do *not* have.
- `out_of_lexicon`: medical terms the annotator would mark that have no lexicon entry. These are always misses, and they feed *strict recall*, so coverage gaps can't hide.
- `tags`: question type, used for the breakdown (lay, abbreviation, misspelling, negation, clinical, brand, no_terms, distractor, hard…).

| Set | Questions | Labeled concepts | Out-of-lexicon terms | Notes |
|---|---|---|---|---|
| `dataset.jsonl` | 90 | 167 | 10 | Development set, written alongside the lexicon |
| `holdout.jsonl` | 40 | 63 | 20 | Written afterward in a different style; the recognizer was not tuned on it |

Both sets include questions with no medical terms, and distractors such as "I ran 5 mi" (where "mi" must not match "MI", myocardial infarction), to measure false positives.

## Metrics

For each question, the predicted concept set is compared with the labeled set:

- **TP**: labeled concepts that were predicted
- **FP**: predicted concepts that were not labeled
- **FN**: labeled concepts that were missed

These counts are summed over all questions (micro-averaging), and then:

- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2PR / (P + R)
- Strict recall = TP / (TP + FN + out-of-lexicon terms)
- Negation accuracy = share of correctly found concepts whose negated/affirmed status matches the label

Results are also broken down by entity category and by question tag. Every error is listed in `eval/results/**/report.md`.

## Methods compared

| Method | What it does | Needs credentials |
|---|---|---|
| `lexicon-exact` | Lexicon phrases and abbreviations only | No |
| `lexicon` | Adds fuzzy matching for misspellings (the default used by the app) | No |
| `llm` | GPT-4 extracts terms as JSON, then each is normalized to a lexicon concept | Yes |
| `hybrid` | Union of `lexicon` and `llm` | Yes |

## Limitations

- Small sets, labeled by a single annotator. There are no inter-annotator agreement figures.
- The development set shares an author with the lexicon, so its scores are optimistic. Use the held-out numbers when quoting results.
- Concept-level matching ignores spans: a concept counts as found if it appears anywhere in the question.
- Negation is rule-based (NegEx-style). It misreads constructions like "heal without surgery" as negation.
