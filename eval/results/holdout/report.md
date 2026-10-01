# Terminology recognition evaluation

- Generated: 2026-10-01T22:43:53+00:00
- Dataset: `holdout.jsonl` (40 questions, 63 labeled concepts, 20 labeled terms outside the lexicon)
- Lexicon: v1.0.0, 181 concepts

## Overall

| Method | Precision | Recall | F1 | Strict recall | Negation accuracy |
|---|---|---|---|---|---|
| lexicon-exact | 100.0% | 85.7% | 92.3% | 65.1% | 96.3% |
| lexicon | 100.0% | 85.7% | 92.3% | 65.1% | 96.3% |

## lexicon-exact: by entity category

| Category | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| anatomy | 100.0% | 66.7% | 80.0% | 2 | 0 | 1 |
| condition | 100.0% | 88.9% | 94.1% | 16 | 0 | 2 |
| medication | 100.0% | 91.7% | 95.7% | 11 | 0 | 1 |
| procedure | 100.0% | 100.0% | 100.0% | 2 | 0 | 0 |
| symptom | 100.0% | 75.0% | 85.7% | 15 | 0 | 5 |
| test | 100.0% | 100.0% | 100.0% | 8 | 0 | 0 |

## lexicon-exact: by question type

| Tag | Precision | Recall | F1 |
|---|---|---|---|
| abbreviation | 100.0% | 100.0% | 100.0% |
| brand | 100.0% | 100.0% | 100.0% |
| clinical | 100.0% | 100.0% | 100.0% |
| condition | 100.0% | 100.0% | 100.0% |
| hard | 100.0% | 40.0% | 57.1% |
| informal | 100.0% | 62.5% | 76.9% |
| lab | 100.0% | 83.3% | 90.9% |
| lay | 100.0% | 70.6% | 82.8% |
| medication | 100.0% | 100.0% | 100.0% |
| negation | 100.0% | 90.9% | 95.2% |
| no_terms | 100.0% | 100.0% | 100.0% |
| oov | 100.0% | 100.0% | 100.0% |
| procedure | 100.0% | 100.0% | 100.0% |
| spelling_variant | 100.0% | 100.0% | 100.0% |
| test | 100.0% | 75.0% | 85.7% |

## lexicon-exact: errors (8 questions)

- **h008** "ive had a temp of 101 for three days and my whole body hurts": missed fever, muscle_pain
- **h011** "My left arm feels weak and my speech was slurred for a few minutes this morning, now it's fine.": missed confusion, weakness
- **h013** "no vomiting, no diarrhea, just nausea after taking my antibiotics": negation wrong for nausea, antibiotic
- **h016** "What do elevated liver enzymes on my bloodwork mean?": missed liver
- **h019** "Neurologist ordered an MRI of my brain for my seizures": missed epilepsy
- **h020** "can you get pneumonia from covid even after being vaccinated": missed vaccine
- **h035** "Do I need a CT if I hit my head and have a headache but didnt pass out?": missed syncope
- **h040** "Had a mini-stroke last month; what meds help prevent another one?": missed stroke

## lexicon: by entity category

| Category | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| anatomy | 100.0% | 66.7% | 80.0% | 2 | 0 | 1 |
| condition | 100.0% | 88.9% | 94.1% | 16 | 0 | 2 |
| medication | 100.0% | 91.7% | 95.7% | 11 | 0 | 1 |
| procedure | 100.0% | 100.0% | 100.0% | 2 | 0 | 0 |
| symptom | 100.0% | 75.0% | 85.7% | 15 | 0 | 5 |
| test | 100.0% | 100.0% | 100.0% | 8 | 0 | 0 |

## lexicon: by question type

| Tag | Precision | Recall | F1 |
|---|---|---|---|
| abbreviation | 100.0% | 100.0% | 100.0% |
| brand | 100.0% | 100.0% | 100.0% |
| clinical | 100.0% | 100.0% | 100.0% |
| condition | 100.0% | 100.0% | 100.0% |
| hard | 100.0% | 40.0% | 57.1% |
| informal | 100.0% | 62.5% | 76.9% |
| lab | 100.0% | 83.3% | 90.9% |
| lay | 100.0% | 70.6% | 82.8% |
| medication | 100.0% | 100.0% | 100.0% |
| negation | 100.0% | 90.9% | 95.2% |
| no_terms | 100.0% | 100.0% | 100.0% |
| oov | 100.0% | 100.0% | 100.0% |
| procedure | 100.0% | 100.0% | 100.0% |
| spelling_variant | 100.0% | 100.0% | 100.0% |
| test | 100.0% | 75.0% | 85.7% |

## lexicon: errors (8 questions)

- **h008** "ive had a temp of 101 for three days and my whole body hurts": missed fever, muscle_pain
- **h011** "My left arm feels weak and my speech was slurred for a few minutes this morning, now it's fine.": missed confusion, weakness
- **h013** "no vomiting, no diarrhea, just nausea after taking my antibiotics": negation wrong for nausea, antibiotic
- **h016** "What do elevated liver enzymes on my bloodwork mean?": missed liver
- **h019** "Neurologist ordered an MRI of my brain for my seizures": missed epilepsy
- **h020** "can you get pneumonia from covid even after being vaccinated": missed vaccine
- **h035** "Do I need a CT if I hit my head and have a headache but didnt pass out?": missed syncope
- **h040** "Had a mini-stroke last month; what meds help prevent another one?": missed stroke
