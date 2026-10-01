# Terminology recognition evaluation

- Generated: 2026-10-01T22:43:53+00:00
- Dataset: `dataset.jsonl` (90 questions, 167 labeled concepts, 10 labeled terms outside the lexicon)
- Lexicon: v1.0.0, 181 concepts

## Overall

| Method | Precision | Recall | F1 | Strict recall | Negation accuracy |
|---|---|---|---|---|---|
| lexicon-exact | 98.7% | 94.0% | 96.3% | 88.7% | 97.5% |
| lexicon | 98.8% | 95.8% | 97.3% | 90.4% | 97.5% |

## lexicon-exact: by entity category

| Category | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| anatomy | 60.0% | 100.0% | 75.0% | 3 | 2 | 0 |
| condition | 100.0% | 95.3% | 97.6% | 61 | 0 | 3 |
| medication | 100.0% | 92.6% | 96.2% | 25 | 0 | 2 |
| procedure | 100.0% | 100.0% | 100.0% | 8 | 0 | 0 |
| symptom | 100.0% | 88.6% | 94.0% | 39 | 0 | 5 |
| test | 100.0% | 100.0% | 100.0% | 21 | 0 | 0 |

## lexicon-exact: by question type

| Tag | Precision | Recall | F1 |
|---|---|---|---|
| abbreviation | 100.0% | 100.0% | 100.0% |
| anatomy | 100.0% | 100.0% | 100.0% |
| brand | 100.0% | 100.0% | 100.0% |
| clinical | 100.0% | 100.0% | 100.0% |
| condition | 100.0% | 100.0% | 100.0% |
| distractor | 0.0% | 100.0% | 0.0% |
| hard | 66.7% | 22.2% | 33.3% |
| lab | 100.0% | 100.0% | 100.0% |
| lay | 96.7% | 78.4% | 86.6% |
| medication | 100.0% | 100.0% | 100.0% |
| misspelling | 100.0% | 57.1% | 72.7% |
| negation | 100.0% | 100.0% | 100.0% |
| no_terms | 100.0% | 100.0% | 100.0% |
| procedure | 100.0% | 100.0% | 100.0% |
| symptom | 100.0% | 100.0% | 100.0% |
| test | 100.0% | 100.0% | 100.0% |

## lexicon-exact: errors (13 questions)

- **q013** "I think I have diabetis, I'm always thirsty and peeing a lot.": missed diabetes
- **q025** "I ran 5 mi this morning and my knees are fine. Any tips for marathon training?": extra knee
- **q039** "I have a burning feeling when I pee and need to go constantly.": missed frequent_urination, painful_urination
- **q042** "Can a herniated disc heal without surgery?": negation wrong for surgery
- **q049** "My grandmother broke her hip and they found osteoporosis.": missed fracture
- **q053** "Started lisinoprill last week and now I have a dry cough.": missed lisinopril
- **q054** "My ankles are swollen at the end of the day. Is that heart failure?": missed edema
- **q065** "Without any symptoms, should I still get a mammogram at 40?": negation wrong for mammogram
- **q072** "Patient negative for COVID, presents with wheezing and productive cough.": negation wrong for cough, wheezing
- **q076** "My heart keeps racing even when I'm sitting still.": missed palpitations; extra heart
- **q077** "Is acetominophen hard on the liver?": missed acetaminophen
- **q082** "How do I know if a cut is infected? It's red and warm around the edges.": missed cellulitis
- **q087** "My stomach hurts after I eat spicy food.": missed abdominal_pain

## lexicon: by entity category

| Category | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| anatomy | 60.0% | 100.0% | 75.0% | 3 | 2 | 0 |
| condition | 100.0% | 96.9% | 98.4% | 62 | 0 | 2 |
| medication | 100.0% | 100.0% | 100.0% | 27 | 0 | 0 |
| procedure | 100.0% | 100.0% | 100.0% | 8 | 0 | 0 |
| symptom | 100.0% | 88.6% | 94.0% | 39 | 0 | 5 |
| test | 100.0% | 100.0% | 100.0% | 21 | 0 | 0 |

## lexicon: by question type

| Tag | Precision | Recall | F1 |
|---|---|---|---|
| abbreviation | 100.0% | 100.0% | 100.0% |
| anatomy | 100.0% | 100.0% | 100.0% |
| brand | 100.0% | 100.0% | 100.0% |
| clinical | 100.0% | 100.0% | 100.0% |
| condition | 100.0% | 100.0% | 100.0% |
| distractor | 0.0% | 100.0% | 0.0% |
| hard | 66.7% | 22.2% | 33.3% |
| lab | 100.0% | 100.0% | 100.0% |
| lay | 96.8% | 81.1% | 88.2% |
| medication | 100.0% | 100.0% | 100.0% |
| misspelling | 100.0% | 100.0% | 100.0% |
| negation | 100.0% | 100.0% | 100.0% |
| no_terms | 100.0% | 100.0% | 100.0% |
| procedure | 100.0% | 100.0% | 100.0% |
| symptom | 100.0% | 100.0% | 100.0% |
| test | 100.0% | 100.0% | 100.0% |

## lexicon: errors (10 questions)

- **q025** "I ran 5 mi this morning and my knees are fine. Any tips for marathon training?": extra knee
- **q039** "I have a burning feeling when I pee and need to go constantly.": missed frequent_urination, painful_urination
- **q042** "Can a herniated disc heal without surgery?": negation wrong for surgery
- **q049** "My grandmother broke her hip and they found osteoporosis.": missed fracture
- **q054** "My ankles are swollen at the end of the day. Is that heart failure?": missed edema
- **q065** "Without any symptoms, should I still get a mammogram at 40?": negation wrong for mammogram
- **q072** "Patient negative for COVID, presents with wheezing and productive cough.": negation wrong for cough, wheezing
- **q076** "My heart keeps racing even when I'm sitting still.": missed palpitations; extra heart
- **q082** "How do I know if a cut is infected? It's red and warm around the edges.": missed cellulitis
- **q087** "My stomach hurts after I eat spicy food.": missed abdominal_pain
