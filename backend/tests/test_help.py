"""Help centre: ready-made answers cost nothing, typed questions use the AI at most once, and it is rate limited."""
import pytest

from app.ai import llm
from app.modules.help import service
from app.modules.help.faq import FAQ
from tests.conftest import as_user


@pytest.fixture(autouse=True)
def fresh_state():
    service.reset_state()
    yield
    service.reset_state()


@pytest.fixture()
def fake_ai(monkeypatch):
    """A pretend model that records every call it receives."""
    calls = []

    def fake(prompt_name, variables, schema):
        calls.append((prompt_name, variables))
        return {"answer": "Open Plan purchases and press Generate plan."}

    monkeypatch.setattr(llm, "complete_json", fake)
    monkeypatch.setattr(llm, "ai_available", lambda: True)
    return calls


@pytest.fixture()
def no_ai(monkeypatch):
    monkeypatch.setattr(llm, "ai_available", lambda: False)


def ask(client, user, question, page="/inventory"):
    return client.post("/api/help/ask", json={"question": question, "page": page}, headers=as_user(user))


def test_faq_is_served_to_any_signed_in_person(client, users):
    r = client.get("/api/help/faq", headers=as_user(users["staff"]))
    assert r.status_code == 200 and len(r.json()) == len(FAQ) >= 10
    assert all(set(f) == {"id", "topic", "question", "answer"} and f["answer"] for f in r.json())
    assert len({f["id"] for f in FAQ}) == len(FAQ)
    assert client.get("/api/help/faq").status_code == 401
    assert client.post("/api/help/ask", json={"question": "hello there"}).status_code == 401


def test_a_faq_question_is_answered_without_calling_the_ai(client, users, fake_ai):
    q = FAQ[0]["question"]
    r = ask(client, users["manager"], q.upper() + "  ")  # case, spaces and punctuation do not matter
    assert r.json() == {"answer": FAQ[0]["answer"], "source": "faq"}
    assert fake_ai == []


def test_faq_works_even_when_the_ai_is_off(client, users, no_ai):
    assert ask(client, users["staff"], FAQ[1]["question"]).json()["source"] == "faq"


def test_a_new_question_asks_the_ai_once_then_is_remembered(client, users, fake_ai):
    first = ask(client, users["manager"], "Where do I click to make a purchase list?")
    again = ask(client, users["manager"], "where do i click to make a purchase list")
    assert (first.json()["source"], again.json()["source"]) == ("ai", "cache")
    assert again.json()["answer"] == first.json()["answer"]
    assert len(fake_ai) == 1


def test_the_ai_only_sees_the_question_role_page_and_guide_never_business_data(client, users, fake_ai):
    ask(client, users["owner"], "How do I do the thing with the orders?", page="/orders")
    name, variables = fake_ai[0]
    assert name == "help" and set(variables) == {"guide", "role", "page", "question"}
    assert (variables["role"], variables["page"]) == ("owner", "/orders")


def test_ai_off_gives_a_friendly_503(client, users, no_ai):
    r = ask(client, users["manager"], "Something not on the list")
    assert r.status_code == 503 and "common questions" in r.json()["detail"]


def test_a_bad_ai_answer_is_treated_as_unavailable(client, users, monkeypatch):
    monkeypatch.setattr(llm, "ai_available", lambda: True)
    monkeypatch.setattr(llm, "complete_json", lambda *a: None)
    assert ask(client, users["manager"], "Something not on the list").status_code == 503


def test_question_length_is_checked(client, users, fake_ai):
    assert ask(client, users["manager"], "hi").status_code == 422
    assert ask(client, users["manager"], "x" * 301).status_code == 422
    assert fake_ai == []


def test_rate_limit_is_three_ai_questions_a_minute(client, users, fake_ai):
    assert service.LIMIT_PER_MINUTE == 3
    for n in range(3):
        assert ask(client, users["manager"], f"Different question number {n}").status_code == 200
    blocked = ask(client, users["manager"], "One more different question")
    assert blocked.status_code == 429 and "3 questions a minute" in blocked.json()["detail"]
    assert len(fake_ai) == 3  # the blocked question never reached the AI
    # free answers still work, and another person is not affected
    assert ask(client, users["manager"], FAQ[2]["question"]).status_code == 200
    assert ask(client, users["owner"], "One more different question").status_code == 200



def test_the_faq_no_longer_mentions_the_removed_ai_features():
    text = " ".join(f["question"] + " " + f["answer"] for f in FAQ).lower()
    assert "quick add" not in text and "suggest" not in text and "from a note" not in text
    ai = next(f for f in FAQ if f["id"] == "ai")["answer"].lower()
    assert "only ai is this help chat" in ai


def test_a_markdown_heavy_model_answer_is_shown_as_clean_plain_text(client, users, monkeypatch):
    messy = "<think>hmm</think>## Steps\n**1.** Open `Plan purchases`.\n* Press *Generate plan*.\n\n\n\n__Done__"
    monkeypatch.setattr(llm, "ai_available", lambda: True)
    monkeypatch.setattr(llm, "complete_json", lambda *a: {"answer": messy})
    r = ask(client, users["manager"], "How do I start a purchase list?").json()
    assert r["answer"] == "Steps\n1. Open Plan purchases.\n- Press Generate plan.\n\nDone"


def test_a_very_long_answer_is_cut_at_a_sentence(client, users, monkeypatch):
    long = "This is one sentence. " * 100
    monkeypatch.setattr(llm, "ai_available", lambda: True)
    monkeypatch.setattr(llm, "complete_json", lambda *a: {"answer": long})
    answer = ask(client, users["manager"], "Tell me everything please").json()["answer"]
    assert len(answer) <= service.MAX_ANSWER_CHARS and answer.endswith(".")
