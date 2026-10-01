import pytest

from medchat.terminology import TerminologyRecognizer


@pytest.fixture(scope="module")
def rec():
    return TerminologyRecognizer()


def ids(rec, text):
    return [m.concept_id for m in rec.recognize(text).matches]


def test_longest_match_wins(rec):
    assert ids(rec, "I have type 2 diabetes") == ["type_2_diabetes"]
    assert ids(rec, "he had a heart attack") == ["myocardial_infarction"]


def test_hyphen_and_space_equivalent(rec):
    assert ids(rec, "type-2 diabetes") == ["type_2_diabetes"]
    assert ids(rec, "chest x-ray") == ["xray"]


def test_lay_terms_and_brands_map_to_concepts(rec):
    assert ids(rec, "high blood pressure") == ["hypertension"]
    assert ids(rec, "tylenol or advil") == ["acetaminophen", "ibuprofen"]


def test_abbreviations(rec):
    result = rec.recognize("HTN and a UTI")
    assert [m.concept_id for m in result.matches] == ["hypertension", "uti"]
    assert all(m.match_type == "abbreviation" for m in result.matches)


def test_ambiguous_abbreviations_are_case_sensitive(rec):
    assert ids(rec, "I was diagnosed with MS") == ["multiple_sclerosis"]
    assert ids(rec, "ms smith called") == []


def test_plurals(rec):
    assert ids(rec, "UTIs and migraines") == ["uti", "migraine"]


def test_misspellings_use_fuzzy_match(rec):
    m = rec.recognize("ibuprofin for my diabetis").matches
    assert [x.concept_id for x in m] == ["ibuprofen", "diabetes"]
    assert all(x.match_type == "fuzzy" for x in m)


def test_fuzzy_can_be_disabled():
    rec = TerminologyRecognizer(enable_fuzzy=False)
    assert rec.recognize("ibuprofin").matches == []


def test_common_words_are_not_fuzzy_matched(rec):
    assert ids(rec, "I should really see a doctor before Monday") == []


@pytest.mark.parametrize("text,negated", [
    ("No fever but a bad cough", {"fever": True, "cough": False}),
    ("denies chest pain", {"chest_pain": True}),
    ("I have a headache. No nausea.", {"headache": False, "nausea": True}),
    ("negative for covid", {"covid_19": True}),
])
def test_negation(rec, text, negated):
    got = {m.concept_id: m.negated for m in rec.recognize(text).matches}
    assert got == negated


def test_spans_point_at_original_text(rec):
    text = "Can I take Advil with Lisinopril?"
    for m in rec.recognize(text).matches:
        assert text[m.start:m.end] == m.text


def test_concept_ids_unique_in_order(rec):
    r = rec.recognize("fever, then more fever, then a cough")
    assert r.concept_ids == ["fever", "cough"]


def test_every_concept_has_definition_and_valid_category(rec):
    valid = {"condition", "symptom", "medication", "test", "procedure", "anatomy"}
    for c in rec.concepts.values():
        assert c.definition, c.id
        assert c.category in valid, c.id
