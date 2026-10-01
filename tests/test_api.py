import pytest
from fastapi.testclient import TestClient

from medchat.api import create_app
from medchat.chat import ChatService
from medchat.config import Settings
from medchat.llm import LLMError, LLMResponse, MockProvider
from medchat.terminology import get_recognizer


class RecordingProvider:
    """Fake GPT-4 that records what it was sent."""

    name = "fake"
    model = "fake-gpt-4"

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        if self.fail:
            raise LLMError("boom")
        return LLMResponse(text="Here is some general information.", model=self.model,
                           provider=self.name, latency_ms=5)


def make_client(provider):
    settings = Settings(llm_provider="mock")
    service = ChatService(settings, provider, get_recognizer())
    return TestClient(create_app(settings, service))


@pytest.fixture
def provider():
    return RecordingProvider()


@pytest.fixture
def client(provider):
    return make_client(provider)


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["concepts"] > 100


def test_chat_returns_reply_and_terms(client):
    r = client.post("/api/chat", json={"message": "Can I take ibuprofen with lisinopril?"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "Here is some general information."
    assert {t["concept_id"] for t in body["terms"]} == {"ibuprofen", "lisinopril"}
    assert body["safety"]["emergency"] is False


def test_recognized_terms_are_passed_to_model(client, provider):
    client.post("/api/chat", json={"message": "No fever but I have a cough"})
    system = provider.calls[-1][0]["content"]
    assert "Fever [symptom] (NEGATED)" in system
    assert "Cough [symptom]:" in system


def test_history_is_forwarded(client, provider):
    history = [{"role": "user", "content": "What is HTN?"},
               {"role": "assistant", "content": "High blood pressure."}]
    client.post("/api/chat", json={"message": "How is it treated?", "history": history})
    roles = [m["role"] for m in provider.calls[-1]]
    assert roles == ["system", "user", "assistant", "user"]


def test_pii_is_redacted_before_model_call(client, provider):
    r = client.post("/api/chat", json={"message": "I'm jane@example.com, is 140/90 high blood pressure?"})
    sent = provider.calls[-1][-1]["content"]
    assert "jane@example.com" not in sent and "[EMAIL]" in sent
    assert r.json()["notices"]


def test_emergency_banner_prepended(client):
    body = client.post("/api/chat", json={"message": "crushing chest pain spreading to my jaw"}).json()
    assert body["safety"]["emergency"] is True
    assert "911" in body["reply"]


def test_crisis_skips_model(client, provider):
    body = client.post("/api/chat", json={"message": "I want to kill myself"}).json()
    assert body["safety"]["crisis"] is True
    assert "988" in body["reply"]
    assert provider.calls == []


def test_model_failure_degrades_gracefully():
    client = make_client(RecordingProvider(fail=True))
    body = client.post("/api/chat", json={"message": "what is asthma"}).json()
    assert body["degraded"] is True
    assert body["terms"][0]["concept_id"] == "asthma"


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "   "}, {"message": "x" * 5000}])
def test_validation_errors(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 422


def test_terms_endpoint(client):
    body = client.post("/api/terms", json={"text": "HTN and CKD"}).json()
    assert body["concept_ids"] == ["hypertension", "ckd"]


def test_concept_lookup(client):
    assert client.get("/api/concepts/asthma").json()["category"] == "condition"
    assert client.get("/api/concepts/nope").status_code == 404


def test_frontend_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "MedChat" in r.text


def test_mock_provider_end_to_end():
    client = make_client(MockProvider())
    body = client.post("/api/chat", json={"message": "What is metformin used for?"}).json()
    assert "Metformin" in body["reply"] and "Demo mode" in body["reply"]


def test_rate_limit():
    client = make_client(RecordingProvider())
    codes = [client.post("/api/chat", json={"message": "what is gout"}).status_code for _ in range(22)]
    assert 429 in codes
