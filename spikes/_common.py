"""Shared helpers for the spikes. Keys come from backend/.env and are never printed."""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")


def key(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        print(json.dumps({"spike": sys.argv[0], "result": "FAIL", "reason": f"{name} is empty in backend/.env"}))
        sys.exit(1)
    return v


def report(spike: str, result: str, **fields) -> None:
    """One JSON line. result is PASS or FAIL. Numbers here are measured, never estimated."""
    print(json.dumps({"spike": spike, "result": result, **fields}))
