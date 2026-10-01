import pytest

from medchat.safety import assess, redact_pii


@pytest.mark.parametrize("text", [
    "I have crushing chest pain and my left arm hurts",
    "My dad's face is drooping and he has slurred speech",
    "I can't breathe",
    "worst headache of my life",
    "my throat is closing after eating peanuts",
])
def test_emergency_detected(text):
    assert assess(text).emergency


@pytest.mark.parametrize("text", [
    "What is a normal blood pressure?",
    "Can I take ibuprofen with food?",
    "I had chest pain last year, what tests check the heart?",
])
def test_routine_questions_not_flagged(text):
    assert not assess(text).emergency


def test_crisis_language_detected():
    assert assess("I want to end my life").crisis
    assert not assess("How do I end my sugar cravings?").crisis


def test_redaction():
    text, found = redact_pii("Email me at jane.doe@example.com or call 617-555-0134. SSN 123-45-6789")
    assert "jane.doe" not in text and "617-555-0134" not in text and "123-45-6789" not in text
    assert set(found) == {"EMAIL", "PHONE", "SSN"}


def test_redaction_leaves_lab_values_alone():
    text, found = redact_pii("My BP was 128/82 and A1c 6.8")
    assert text == "My BP was 128/82 and A1c 6.8"
    assert found == []
