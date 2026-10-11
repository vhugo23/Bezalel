"""Checks the real Backboard API with the key in backend/.env, then cleans up after itself.

    cd backend
    python scripts/backboard_check.py

1. Raw API: create a throwaway assistant, add / search / list / delete a memory, delete the assistant.
   Prints the reply's field names (never values or the key) so we learn the undocumented shapes.
2. The app's memory layer (MEMORY_BACKEND=backboard): remember, recall, forget, with no fallback allowed.
Uses no database (DATABASE_URL is ignored here) and touches no real user's memories.
"""
import asyncio
import os
import secrets
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import httpx  # noqa: E402

from app import config  # noqa: E402  (loads backend/.env)
from app.core import memory, store  # noqa: E402

RESULTS: list[bool] = []
CREATED: list[str] = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("  PASS " if ok else "  FAIL ") + name + (f"   <- {str(detail)[:200]}" if detail and not ok else ""))
    return ok


async def raw(c: httpx.AsyncClient):
    print("1. raw Backboard API")
    r = await c.post("/assistants", json={"name": f"prepcrew-check-{secrets.token_hex(3)}",
                                          "system_prompt": "Temporary assistant for a connectivity check."})
    if not check("create assistant", r.status_code < 300, f"{r.status_code} {r.text[:150]}"):
        return
    body = r.json(); aid = body.get("assistant_id") or body.get("id"); CREATED.append(aid)
    print(f"         create reply fields: {sorted(body)}")
    r = await c.post(f"/assistants/{aid}/memories", json={"content": "Gap: has never used an oscilloscope.",
                                                          "metadata": {"source": "check"}})
    check("add memory", r.status_code < 300, f"{r.status_code} {r.text[:150]}")
    add = r.json() if r.content else {}
    mid = memory._memory_id(add)
    print(f"         add reply fields: {sorted(add)}   -> memory id found: {bool(mid)}")
    check("add memory reply carries an id the app can use for deletion", mid is not None, sorted(add))
    hits = []
    for _ in range(10):  # indexing can lag a little behind the add
        r = await c.post(f"/assistants/{aid}/memories/search", json={"query": "oscilloscope experience", "limit": 5})
        hits = r.json().get("memories", []) if r.status_code < 300 else []
        if hits:
            break
        await asyncio.sleep(1.5)
    check("search finds it", any("oscilloscope" in h.get("content", "") for h in hits), r.text[:150])
    if hits:
        print(f"         search result fields: {sorted(hits[0])}")
    r = await c.get(f"/assistants/{aid}/memories")
    listed = r.json().get("memories", []) if r.status_code < 300 else []
    check("list memories", r.status_code < 300 and listed, f"{r.status_code} {r.text[:150]}")
    target = mid or (listed[0].get("id") if listed else None)
    if target:
        r = await c.delete(f"/assistants/{aid}/memories/{target}")
        check("delete memory", r.status_code < 300, f"{r.status_code} {r.text[:150]}")
        left = (await c.get(f"/assistants/{aid}/memories")).json().get("memories", [])
        check("memory is gone after delete", not any(m.get("id") == target for m in left), len(left))


async def app_layer():
    print("\n2. the app's memory layer (MEMORY_BACKEND=backboard, fallback not allowed)")
    config.MEMORY_BACKEND, config.DATABASE_URL = "backboard", ""
    owner = f"check-{secrets.token_hex(4)}"
    ref = await memory.remember(owner, "Strength: explained Ohm's law clearly.", {"source": "check"})
    found = await store.find_records("bb_assistant", "owner_id", owner, limit=1)
    if found:
        CREATED.append(found[0]["data"]["assistant_id"])
    check("remember stored it in Backboard (not the fallback)", ref["backend"] == "backboard", ref["backend"])
    got = []
    for _ in range(10):
        got = await memory.recall(owner, "Ohm's law", limit=3)
        if got:
            break
        await asyncio.sleep(1.5)
    check("recall returns it", any("Ohm" in t for t in got), got)
    check("forget deletes it", await memory.forget([ref]) == 1, ref)


async def main():
    if not config.BACKBOARD_API_KEY:
        sys.exit("BACKBOARD_API_KEY is empty in backend/.env")
    start = time.perf_counter()
    async with httpx.AsyncClient(base_url=config.BACKBOARD_BASE_URL, timeout=20,
                                 headers={"X-API-Key": config.BACKBOARD_API_KEY}) as c:
        try:
            await raw(c)
            await app_layer()
        finally:
            print("\n3. cleanup")
            for aid in CREATED:
                try:
                    r = await c.delete(f"/assistants/{aid}")
                    print(f"  deleted check assistant: {r.status_code < 300}")
                except Exception as e:
                    print(f"  could not delete a check assistant ({type(e).__name__}); remove 'prepcrew-check-*' "
                          "or 'PrepCrew candidate check-*' in the Backboard dashboard")
    print(f"\n{sum(RESULTS)} of {len(RESULTS)} checks passed in {time.perf_counter() - start:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
