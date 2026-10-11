"""Integration verification against configured Tiger Data. Fixture writes are rolled back."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4
import asyncpg
from dotenv import dotenv_values

async def main():
    root=Path(__file__).resolve().parents[2]
    conn=await asyncpg.connect(dotenv_values(root/'.env')['DATABASE_URL'],server_settings={'search_path':'prepcrew,public'})
    try:
        tables={r[0] for r in await conn.fetch("SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_schema='prepcrew'")}
        assert tables=={'session_events','skill_assessments','metrics'}
        aggregates={r[0] for r in await conn.fetch("SELECT view_name FROM timescaledb_information.continuous_aggregates WHERE view_schema='prepcrew'")}
        assert aggregates=={'mastery_hourly','latency_1m'}
        forbidden=await conn.fetch("SELECT conname FROM pg_constraint WHERE contype='f' AND confrelid IN ('prepcrew.session_events'::regclass,'prepcrew.skill_assessments'::regclass,'prepcrew.metrics'::regclass)")
        assert not forbidden
        assert not await conn.fetchval("SELECT count(*) FROM timescaledb_information.jobs WHERE hypertable_schema='prepcrew' AND proc_name='policy_compression'")
        tx=conn.transaction();await tx.start()
        try:
            user,track,scenario,session,run=[str(uuid4()) for _ in range(5)]
            await conn.execute('INSERT INTO users(id) VALUES($1)',user)
            await conn.execute("INSERT INTO tracks(id,user_id,domain_id,engine_id,layer,title,source) VALUES($1,$2,'sw','conceptual',3,'Integration fixture','catalog')",track,user)
            await conn.execute("INSERT INTO scenarios(id,track_id,engine_id,engine_version) VALUES($1,$2,'conceptual','1')",scenario,track)
            await conn.execute('INSERT INTO sessions(id,user_id,track_id,scenario_id) VALUES($1,$2,$3,$4)',session,user,track,scenario)
            await conn.execute("INSERT INTO evaluator_runs(id,session_id,evaluator) VALUES($1,$2,'test')",run,session)
            try:
                async with conn.transaction():
                    await conn.execute("INSERT INTO claims(id,run_id,session_id,text,polarity,check_status) VALUES($1,$2,$3,'unsupported','strength','verified')",str(uuid4()),run,session)
                raise AssertionError('Empty verified claim was accepted')
            except asyncpg.CheckViolationError as error:
                assert error.constraint_name=='claims_verified_has_evidence'
            first=await conn.fetchval("INSERT INTO session_events(session_id,kind) VALUES($1,'note') RETURNING seq",session)
            second=await conn.fetchval("INSERT INTO session_events(session_id,kind) VALUES($1,'note') RETURNING seq",session)
            assert second>first
            await conn.execute("INSERT INTO skill_assessments(user_id,skill_id,score,source,ts) VALUES($1,'sw.system_design',80,'session',now()),($1,'sw.system_design',20,'session',now()-interval '2 hours')",user)
            assert await conn.fetchval("SELECT score FROM user_skills WHERE user_id=$1 AND skill_id='sw.system_design'",user)==80
            assert await conn.fetchval('SELECT count(*) FROM mastery_hourly WHERE user_id=$1',user)>=1
        finally:
            await tx.rollback()
        print(json.dumps({'hypertables':sorted(tables),'aggregates':sorted(aggregates),'evidence_constraint':'passed','no_hypertable_foreign_keys':'passed','seq_order':'passed','delayed_mastery':'passed','fixture_writes':'rolled back'},indent=2))
    finally:
        await conn.close()

asyncio.run(main())
