"""Shared settings precedence: process environment, root .env, backend .env.

An explicit empty value disables a setting; it must not revive a fallback key.
Paths are anchored to this repository rather than the caller's working directory.
"""
import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


def settings(root: Path = ROOT) -> dict[str, str]:
    values = {}
    for path in (root / 'backend' / '.env', root / '.env'):
        values.update({key: value for key, value in dotenv_values(path, interpolate=False).items()
                       if value is not None})
    return {**values, **os.environ}


def load_environment(root: Path = ROOT) -> None:
    for key, value in settings(root).items():
        os.environ.setdefault(key, value)
