import json
from pathlib import Path

CIRCUITS_PATH = Path(__file__).resolve().parent / "data" / "circuits.json"


def load_circuits() -> dict:
    """circuits.json shape (fill in): {circuit_id: {"hidden_fault": "", "readings": {node: value}}}
    Server-side only, so the client can never see the fault."""
    return json.loads(CIRCUITS_PATH.read_text())


def probe(circuit_id: str, node: str) -> str:
    """TODO: return the stored reading for this node; the caller logs the probe order."""
    raise NotImplementedError
