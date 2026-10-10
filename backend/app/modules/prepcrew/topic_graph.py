import json
from pathlib import Path

TOPICS_PATH = Path(__file__).resolve().parent / "data" / "topics.json"


def load_topics() -> dict:
    """topics.json shape (fill in): {topic_id: {"title": "", "prerequisites": []}}"""
    return json.loads(TOPICS_PATH.read_text())


def prerequisites(topic_id: str) -> list[str]:
    """TODO: walk the prerequisite edges."""
    return []
