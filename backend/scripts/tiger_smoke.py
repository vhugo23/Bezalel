"""End-to-end check of the backend against the real database, without touching your real tables.

    cd backend
    python scripts/tiger_smoke.py

What it does:
  1. Creates a throwaway schema (smoke_xxxxxx) in the database from DATABASE_URL in backend/.env.
  2. Runs sql/schema.sql and sql/prepcrew.sql inside it and lists the Tiger hypertables and aggregates made.
  3. Starts the backend on port 8799 pointed at that schema (fake AI and voice, so no API credits are used).
  4. Drives the whole flow: plan, session, typed and websocket turns, probes, end, SSE, report, metrics, deletion.
  5. Stops the server and drops the throwaway schema (pass --keep to keep it for inspection).
Your real tables in "public" are never read or written. The connection string is never printed.
"""
import argparse
import asyncio
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import websockets  # noqa: E402

from app import config  # noqa: E402  (loads backend/.env)

PORT = 8799
RESULTS: list[bool] = []


def check(name: str, ok: bool, detail="") -> bool:
    RESULTS.append(bool(ok))
    print(("  PASS " if ok else "  FAIL ") + name + (f"   <- {str(detail)[:200]}" if detail and not ok else ""))
    return ok


def with_search_path(dsn: str, path: str) -> str:
    """path is a comma separated search_path, e.g. 'smoke_ab12cd,public'. New tables go to the first one."""
    u = urllib.parse.urlsplit(dsn)
    q = urllib.parse.parse_qsl(u.query) + [("search_path", path)]
    return urllib.parse.urlunsplit(u._replace(query=urllib.parse.urlencode(q)))


def strip_timescale(sql: str) -> str:
    """Only for --no-timescale (plain Postgres without the extension)."""
    sql = sql.replace("CREATE EXTENSION IF NOT EXISTS timescaledb;", "")
    sql = re.sub(r"SELECT (create_hypertable|add_[a-z_]+policy)\(.*?\);", "", sql, flags=re.S)
    return re.sub(r"CREATE MATERIALIZED VIEW IF NOT EXISTS \w+\s+WITH \(timescaledb.*?WITH NO DATA;", "", sql, flags=re.S)


async def extension_schema(dsn: str) -> str | None:
    conn = await asyncpg.connect(dsn)
    try:
        return await conn.fetchval("select n.nspname from pg_extension e join pg_namespace n on n.oid = e.extnamespace "
                                   "where e.extname = 'timescaledb'")
    finally:
        await conn.close()


async def setup_schema(dsn: str, schema: str, ext_schema: str | None, no_timescale: bool) -> bool:
    conn = await asyncpg.connect(dsn)
    try:
        if not no_timescale:
            ver = await conn.fetchval("select extversion from pg_extension where extname = 'timescaledb'")
            if not check("timescaledb extension is installed in this database", ver is not None, "not installed"):
                return False  # never let CREATE EXTENSION land inside the throwaway schema
            print(f"         timescaledb {ver} (functions in schema '{ext_schema}')")
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        # throwaway schema first: every new table goes there. The extension's schema second, only so that
        # create_hypertable and friends resolve.
        await conn.execute(f'SET search_path TO "{schema}", "{ext_schema or "public"}"')
        ok = True
        for f in ("sql/schema.sql", "sql/prepcrew.sql"):
            text = Path(f).read_text(encoding="utf-8")
            if no_timescale:
                text = strip_timescale(text)
            try:
                await conn.execute(text)
                check(f"{f} runs", True)
            except Exception as e:
                ok = check(f"{f} runs", False, f"{type(e).__name__}: {e}") and ok
        tables = await conn.fetchval(
            "select count(*) from information_schema.tables where table_schema=$1 and table_type='BASE TABLE'", schema)
        print(f"         {tables} tables created in {schema}")
        if not no_timescale:
            hts = [r[0] for r in await conn.fetch(
                "select hypertable_name from timescaledb_information.hypertables where hypertable_schema=$1 order by 1", schema)]
            caggs = [r[0] for r in await conn.fetch(
                "select view_name from timescaledb_information.continuous_aggregates where view_schema=$1 order by 1", schema)]
            check("hypertables created", len(hts) > 0, hts)
            print(f"         hypertables: {hts}")
            check("continuous aggregates created", len(caggs) > 0, caggs)
            print(f"         continuous aggregates: {caggs}")
        return ok
    finally:
        await conn.close()


async def drive(dsn_schema: str, schema: str, has_scenario: bool):
    base, ws_base = f"http://127.0.0.1:{PORT}", f"ws://127.0.0.1:{PORT}"
    db = await asyncpg.connect(dsn_schema)
    try:
        async with httpx.AsyncClient(base_url=base, timeout=30) as c:
            h = (await c.get("/api/health")).json()
            check("server is using the database", h.get("database") is True, h)
            r = (await c.post("/api/records/note", json={"data": {"a": 1}, "owner_id": "smoke"})).json()
            m = (await c.patch(f"/api/record/{r['id']}", json={"data": {"b": 2}})).json()
            check("generic record write + JSON merge", m.get("data") == {"a": 1, "b": 2}, m)
            plan = (await c.post("/api/plans", json={"job_posting": "Embedded intern", "resume": "Motor driver",
                                                     "user_id": "smoke_user"})).json()
            check("plan", "plan_id" in plan, plan)
            s = await c.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "smoke_user", "consent": True})
            check("session", s.status_code == 200, s.text); sid = s.json()["session_id"]
            t = await c.post(f"/api/sessions/{sid}/turns", json={"answer": "I measured the supply first."})
            check("typed turn", t.status_code == 200, t.text)
            async with websockets.connect(f"{ws_base}/ws/voice/{sid}") as w:
                first = json.loads(await asyncio.wait_for(w.recv(), 10))
                check("voice websocket opens", first.get("type") == "state", first)
                await w.send(json.dumps({"type": "text_answer", "text": "Then I probed the LED."}))
                seen = []
                try:
                    while "tts_done" not in seen:
                        msg = await asyncio.wait_for(w.recv(), 10)
                        if isinstance(msg, str):
                            seen.append(json.loads(msg).get("type"))
                except asyncio.TimeoutError:
                    pass
                check("voice websocket answer round trip", "transcript_final" in seen, seen)
            if has_scenario:
                p0 = (await c.post(f"/api/sessions/{sid}/probe", json={"node": "n2", "scenario_id": "led_reversed"})).json()
                p1 = (await c.post(f"/api/sessions/{sid}/probe", json={"action": "swap_part", "node": "D1",
                                                                         "scenario_id": "led_reversed"})).json()
                check("probe events numbered by the server (0, 1)", (p0.get("seq"), p1.get("seq")) == (0, 1), (p0, p1))
            e = (await c.post(f"/api/sessions/{sid}/end")).json()
            check("end returns at once", e.get("status") == "grading", e)
            events = []
            async with c.stream("GET", f"/api/sessions/{sid}/events", timeout=60) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("event: "):
                        events.append(line[7:])
                        if events[-1] == "grading_complete":
                            break
            check("SSE stream reaches grading_complete", events[-1:] == ["grading_complete"], events)
            check("report", (await c.get(f"/api/sessions/{sid}/report")).json().get("status") == "graded")
            check("metrics", (await c.get(f"/api/metrics/{sid}")).json().get("turn_total_ms") is not None)
            check("mastery", (await c.get("/api/mastery", params={"user_id": "smoke_user"})).status_code == 200)
            stored = await db.fetchval(f'select count(*) from "{schema}".events where subject_id=$1', sid)
            check(f"rows stored in {schema} (not in your real tables)", stored >= 3, stored)
            leaked = await db.fetchval("select count(*) from information_schema.tables "
                                       "where table_schema = 'public' and table_name = 'events'")
            if leaked:
                n = await db.fetchval("select count(*) from public.events where subject_id=$1", sid)
                check("nothing written to public.events", n == 0, n)
            d = await c.delete(f"/api/sessions/{sid}")
            check("delete session", d.status_code == 200, d.text)
            left = await db.fetchval(f'select count(*) from "{schema}".events where subject_id=$1', sid)
            plan_left = await db.fetchval(f'select count(*) from "{schema}".records where id=$1', plan["plan_id"])
            check("deletion removed the session's events", left == 0, left)
            check("deletion removed the plan (resume text)", plan_left == 0, plan_left)
    finally:
        await db.close()


async def drop_schema(dsn: str, schema: str):
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
        print(f"  dropped {schema}")
    except Exception as e:
        print(f"  could not drop {schema}: {type(e).__name__}: {e}")
        print(f'  drop it yourself in the Tiger SQL editor:  DROP SCHEMA "{schema}" CASCADE;')
    finally:
        await conn.close()


def wait_for_server(proc) -> bool:
    for _ in range(60):
        if proc.poll() is not None:
            return False
        try:
            if httpx.get(f"http://127.0.0.1:{PORT}/api/health", timeout=1).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep the throwaway schema afterwards")
    ap.add_argument("--no-timescale", action="store_true", help="plain Postgres without TimescaleDB (local testing)")
    args = ap.parse_args()

    dsn = config.DATABASE_URL
    if not dsn:
        sys.exit("DATABASE_URL is empty in backend/.env")
    schema = "smoke_" + secrets.token_hex(3)
    host = (urllib.parse.urlsplit(dsn).hostname or "")
    print(f"database: ...{host[-24:]}   throwaway schema: {schema}\n")

    scenario_src = BACKEND.parent / "contracts" / "examples" / "led_reversed.json"
    scenario_dst = BACKEND / "app" / "modules" / "prepcrew" / "data" / "scenarios" / "led_reversed.json"
    added_scenario = False
    proc = None
    created = False
    try:
        print("1. schema")
        created = True  # set before CREATE so a partial schema is still dropped
        ext_schema = asyncio.run(extension_schema(dsn)) or "public"
        path = f"{schema},{ext_schema}"
        if not asyncio.run(setup_schema(dsn, schema, ext_schema, args.no_timescale)):
            print("\nschema setup failed, skipping the server checks")
            return
        if scenario_src.exists() and not scenario_dst.exists():
            shutil.copyfile(scenario_src, scenario_dst)
            added_scenario = True
        print("\n2. backend on the throwaway schema (fake AI and voice)")
        env = {**os.environ, "DATABASE_URL": with_search_path(dsn, path), "LLM_PROVIDER": "fake",
               "VOICE_PROVIDER": "fake", "MEMORY_BACKEND": "", "APP_API_KEY": ""}
        log = open(BACKEND / "scripts" / "tiger_smoke_server.log", "w", encoding="utf-8")
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)],
                                cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT)
        if not check("server started", wait_for_server(proc), "see scripts/tiger_smoke_server.log"):
            return
        asyncio.run(drive(with_search_path(dsn, path), schema, scenario_dst.exists()))
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
        if added_scenario:
            scenario_dst.unlink(missing_ok=True)
        print("\n3. cleanup")
        if created and not args.keep:
            asyncio.run(drop_schema(dsn, schema))
        elif created:
            print(f"  kept {schema} (--keep)")
        print(f"\n{sum(RESULTS)} of {len(RESULTS)} checks passed")
        if proc is not None:
            print("server log: backend/scripts/tiger_smoke_server.log")


if __name__ == "__main__":
    main()
