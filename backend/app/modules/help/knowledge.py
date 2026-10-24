"""Pick the few parts of the guide that matter for one question, so each typed question sends little text.

Sending the whole guide (about 2,600 words) with every question is wasteful. Instead the guide file is split into
its "== TITLE ==" sections and only the best-matching ones are sent, plus the ready-made answers that match. If
nothing matches (for example a question in Bahasa Malaysia), the whole guide is sent so the answer is still good.
"""
import re

from app.modules.help.faq import FAQ, GUIDE_FILE, PAGES, guide_text

MAX_SECTIONS, MAX_FAQ = 2, 3
ALWAYS = "THE BIG PICTURE"  # a short opening section that is always included

STOP = set(
    "the and for are how what when where which who why can does did you your our this that with from have has "
    "not but all any its about into than then them they there here will would should could please tell explain "
    "give show want need know like get make use used using app way thing things detail detailed".split()
)


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in STOP}


def _sections() -> tuple[str, dict[str, str]]:
    """(the text before the first section, {title: body}) from guide.md."""
    text = GUIDE_FILE.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^== (.+?) ==\s*$", text)
    return parts[0].strip(), {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def _score(question: set[str], title: str, body: str) -> int:
    return 3 * len(question & _words(title)) + len(question & _words(body))


def relevant_guide(question: str) -> str:
    """The guide text to send with this question."""
    intro, sections = _sections()
    q = _words(question)
    ranked = sorted(((_score(q, t, b), t) for t, b in sections.items() if t != ALWAYS), reverse=True)
    chosen = [t for s, t in ranked[:MAX_SECTIONS] if s > 0]
    faq = sorted(((len(q & _words(f["question"] + " " + f["answer"])), i) for i, f in enumerate(FAQ)), reverse=True)
    picked = [FAQ[i] for s, i in faq[:MAX_FAQ] if s > 0]
    if not chosen and not picked:
        return guide_text()  # nothing matched: send everything rather than guess
    out = [intro, f"== {ALWAYS} ==\n{sections.get(ALWAYS, '')}"]
    out += [f"== {t} ==\n{sections[t]}" for t in chosen]
    out.append(f"Pages: {PAGES}")
    out += [f"Ready-made answer to '{f['question']}':\n{f['answer']}" for f in picked]
    return "\n\n".join(p for p in out if p)
