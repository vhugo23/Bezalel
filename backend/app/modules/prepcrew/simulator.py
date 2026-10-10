"""Circuit readings. Scenario files follow contracts/netlist.schema.json and live in data/scenarios/<id>.json.
Until the DC solver exists, readings come from the scenario's `expected_voltages` (the contract's fallback):
the "faulted" state for debug scenarios, "healthy" otherwise. Faults never leave the server."""
import json
from functools import lru_cache
from pathlib import Path

SCENARIOS_DIR = Path(__file__).resolve().parent / "data" / "scenarios"


class UnknownScenario(LookupError):
    pass


class UnknownNode(LookupError):
    pass


@lru_cache(maxsize=64)
def load_scenario(scenario_id: str) -> dict:
    if not scenario_id.replace("_", "").isalnum():
        raise UnknownScenario(scenario_id)
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.is_file():
        raise UnknownScenario(scenario_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_scenarios() -> list[str]:
    return sorted(p.stem for p in SCENARIOS_DIR.glob("*.json"))


def read_voltage(scenario_id: str, node: str) -> float:
    sc = load_scenario(scenario_id)
    volts = sc.get("expected_voltages", {})
    state = "faulted" if sc.get("kind") == "debug" and "faulted" in volts else "healthy"
    table = volts.get(state, {})
    if node not in table:
        raise UnknownNode(node)
    return float(table[node])
    # TODO: replace with the DC nodal solver; tests must show it matches expected_voltages.
