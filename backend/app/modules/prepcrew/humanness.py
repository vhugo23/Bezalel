"""Cheap, deterministic checks for chatbot-sounding interviewer lines. Runs on every live reply in microseconds.
Patterns come from the humanizer guide (Wikipedia "Signs of AI writing"), narrowed to what shows up when a line
is spoken aloud. `sanitize` fixes the mechanical tells. `check` names the rest so they can be counted.

Live turns are not regenerated on a violation (that costs a second), they are logged and counted, see interviewer.py."""
import re

MAX_WORDS = 40

# phrase patterns -> violation code
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("praise", re.compile(r"\b(great|excellent|fantastic|wonderful|awesome|perfect|good|nice) (question|answer|point|job|explanation)\b"
                          r"|\bthat'?s (a )?(great|excellent|fantastic|wonderful|really good|really interesting)\b", re.I)),
    ("servile", re.compile(r"\b(absolutely|certainly|of course|i hope this helps|let me know|happy to help|thanks for sharing|thank you for sharing)\b", re.I)),
    ("ai_vocab", re.compile(r"\b(delve|delving|testament|pivotal|tapestry|vibrant|showcas\w+|underscor\w+|fostering|intricate|intricacies|multifaceted|landscape)\b", re.I)),
    ("filler", re.compile(r"\b(it'?s important to note|it is important to note|in order to|at its core|at this point in time|due to the fact)\b", re.I)),
    ("connective", re.compile(r"^\s*(additionally|furthermore|moreover|in conclusion|overall),", re.I)),
    ("negative_parallelism", re.compile(r"\bnot (just|only|merely|simply)\b.{0,60}\bbut\b|\bit'?s not (just|only|merely) ", re.I)),
    ("coming_back", re.compile(r"\b(coming|going|circling) back to\b|\blet'?s (jump|get|go) back to\b", re.I)),
]
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_DASH = re.compile(r"\s*[—–]\s*")
_CURLY = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
_WORD = re.compile(r"[a-z0-9']+")
STOP = {"that", "this", "with", "have", "what", "your", "from", "were", "they", "them", "then", "than", "about",
        "would", "could", "should", "there", "their", "which", "when", "where", "into", "just", "like", "also",
        "been", "does", "did", "how", "why", "the", "and", "for", "you", "was", "are", "but", "not", "its"}


def sanitize(text: str) -> str:
    """Fix the mechanical tells: dashes, curly quotes, emojis, stray whitespace."""
    text = _EMOJI.sub("", text).translate(_CURLY)
    text = _DASH.sub(", ", text)
    return " ".join(text.split())


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def first_word(text: str) -> str:
    w = words(text)
    return w[0] if w else ""


def restated_fraction(reply: str, answer: str) -> float:
    """Share of the reply's content words that the candidate just said. High means the reply mostly parrots them."""
    content = [w for w in words(reply) if len(w) > 3 and w not in STOP]
    if len(content) < 4:
        return 0.0
    said = set(words(answer))
    return sum(1 for w in content if w in said) / len(content)


def check(reply: str, last_answer: str = "", previous_replies: list[str] | None = None) -> list[str]:
    """Violation codes for one spoken line. Empty list means it passes."""
    found = [code for code, rx in _PATTERNS if rx.search(reply)]
    if "—" in reply or "–" in reply:
        found.append("dash")
    if _EMOJI.search(reply):
        found.append("emoji")
    if len(words(reply)) > MAX_WORDS:
        found.append("too_long")
    if last_answer and restated_fraction(reply, last_answer) >= 0.6:
        found.append("restates_answer")
    recent = [first_word(r) for r in (previous_replies or [])[-2:]]
    if len(recent) == 2 and recent[0] == recent[1] == first_word(reply) != "":
        found.append("same_opening")
    return found
