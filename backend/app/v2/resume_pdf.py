"""Plain, single-column PDF of a resume's text. Real text, no tables or images, so it stays machine-readable."""


def render(title: str, body: str) -> bytes:
    """Return PDF bytes for a resume body (at most 60,000 characters of plain text or light Markdown)."""
    raise NotImplementedError
