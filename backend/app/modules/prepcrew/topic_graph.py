"""Skill graph. data/topics.json shape: {"<skill_id>": {"title": "", "prerequisites": ["<skill_id>", ...]}}"""
import json
from pathlib import Path

TOPICS_PATH = Path(__file__).resolve().parent / "data" / "topics.json"


def load_topics() -> dict:
    return json.loads(TOPICS_PATH.read_text(encoding="utf-8"))


def prerequisites(skill_id: str) -> list[str]:
    return list(load_topics().get(skill_id, {}).get("prerequisites", []))
