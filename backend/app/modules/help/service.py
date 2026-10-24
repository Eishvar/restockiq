"""Help centre: free answers first, the AI only for questions nobody has asked yet.

Order of answers (cheapest first):
  1. the question is one of the ready-made FAQ questions  -> cached answer, no AI call
  2. the same question was asked before (same role)        -> remembered answer, no AI call
  3. otherwise the AI is asked, with the guide as its only source, and the answer is remembered

Cost guards: a short question limit, a per-person rate limit, and the answer cache. The AI is never sent any of
the business's data, only the question, the person's role and the page they are on.
"""
import re
import time
from collections import OrderedDict, deque
from threading import Lock

from fastapi import HTTPException

from app.ai import llm
from app.modules.help.faq import FAQ, guide_text
from app.modules.help.schemas import AskIn, AskOut, LlmHelpAnswer
from app.modules.settings.models import User

MIN_CHARS, MAX_CHARS = 3, 300
MAX_ANSWER_CHARS = 1200
CACHE_SIZE = 300
LIMIT_PER_MINUTE, LIMIT_PER_HOUR = 6, 40  # AI calls per person; FAQ clicks and remembered answers are not counted

UNAVAILABLE = "The AI helper is not available right now. Try one of the common questions below, or ask your owner."

_lock = Lock()
_cache: OrderedDict[tuple[str, str], str] = OrderedDict()
_calls: dict[int, deque[float]] = {}


def reset_state() -> None:
    """Forget remembered answers and rate-limit counters (used by the tests)."""
    with _lock:
        _cache.clear()
        _calls.clear()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


_FAQ_BY_QUESTION = {_norm(f["question"]): f["answer"] for f in FAQ}


def _check_rate(user_id: int) -> None:
    now = time.monotonic()
    with _lock:
        recent = _calls.setdefault(user_id, deque())
        while recent and now - recent[0] > 3600:
            recent.popleft()
        last_minute = sum(1 for t in recent if now - t <= 60)
        if last_minute >= LIMIT_PER_MINUTE or len(recent) >= LIMIT_PER_HOUR:
            raise HTTPException(429, "You are asking quite fast. Please wait a minute, or try the common questions below.")
        recent.append(now)


def ask(user: User, body: AskIn) -> AskOut:
    question = " ".join(body.question.split())
    if len(question) < MIN_CHARS:
        raise HTTPException(422, "Please type a question.")
    if len(question) > MAX_CHARS:
        raise HTTPException(422, f"Please keep your question under {MAX_CHARS} characters.")
    key = _norm(question)

    if key in _FAQ_BY_QUESTION:
        return AskOut(answer=_FAQ_BY_QUESTION[key], source="faq")

    cache_key = (user.role, key)
    with _lock:
        if cache_key in _cache:
            _cache.move_to_end(cache_key)
            return AskOut(answer=_cache[cache_key], source="cache")

    if not llm.ai_available():
        raise HTTPException(503, UNAVAILABLE)
    _check_rate(user.id)
    result = llm.complete_json(
        "help",
        {"guide": guide_text(), "role": user.role, "page": body.page[:60] or "unknown", "question": question},
        LlmHelpAnswer,
    )
    answer = (result or {}).get("answer", "").strip()
    if not answer:
        raise HTTPException(503, UNAVAILABLE)
    answer = answer[:MAX_ANSWER_CHARS]

    with _lock:
        _cache[cache_key] = answer
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return AskOut(answer=answer, source="ai")
