-- PrepCrew schema v2.3 (v2.3: talk-while-drawing whiteboard with interviewer annotations). Postgres 15+ on Tiger Data (TimescaleDB 2.13+). Idempotent: safe to re-run.
--
-- Principles
--   1. Relational where the app joins, filters or enforces rules. JSONB only for engine-specific payloads
--      (a netlist, a C snippet, an event body) that differ per engine and are never joined on.
--   2. Three things are time-series and live in hypertables: session_events (the evidence log),
--      skill_assessments (mastery over time), metrics (latency and measured values).
--   3. Every claim shown to a user must point at real events. The DB enforces it (see claims).
--   4. Generation is auditable and cacheable: every model call is a generation_jobs row, and a scenario
--      is only offered once a deterministic validity check has passed.
--   5. Memory is implicit. It is derived from graded claims and consumed by the interviewer opener,
--      the retest queue and the track "reason" tags. There is no memory UI.
--
-- Foreign-key rule: a hypertable may reference a normal table, but nothing may reference a hypertable.
-- Claims therefore point at events by (session_id, seq) and the evidence checker verifies them.

CREATE EXTENSION IF NOT EXISTS timescaledb;
-- Optional, only if MEMORY_BACKEND=postgres and you want semantic recall:
-- CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================================================
-- 1. IDENTITY AND INTAKE  (onboarding screen)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    display_name TEXT,
    email        TEXT UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id          TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    target_role      TEXT,
    target_companies TEXT[] NOT NULL DEFAULT '{}',
    struggles        TEXT[] NOT NULL DEFAULT '{}',          -- tapped chips: "Linux & servers", ...
    resume_text      TEXT,                                  -- drives the project deep-dive opener
    links            JSONB NOT NULL DEFAULT '{}'::jsonb,    -- {github, resume_url}
    preferences      JSONB NOT NULL DEFAULT '{}'::jsonb,    -- {whiteboard_mode:'inline'|'linked', voice:true}
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Anything the user hands us that tracks can be grounded in: resume, GitHub repo, job posting,
-- notes, an uploaded interview recording. `extracted` holds structured facts (projects, stack, questions asked).
CREATE TABLE IF NOT EXISTS source_documents (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('resume','repo','job_posting','notes','recording','other')),
    title      TEXT,
    body       TEXT,
    blob_key   TEXT,
    extracted  JSONB NOT NULL DEFAULT '{}'::jsonb,         -- {projects:[{name,summary,tech[]}], questions:[...]}
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS source_documents_user_idx ON source_documents (user_id, kind, created_at DESC);

-- The most valuable input: the question that tripped the user. Also appended after sessions.
CREATE TABLE IF NOT EXISTS failed_questions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    company    TEXT,
    source_doc_id TEXT REFERENCES source_documents(id) ON DELETE SET NULL,   -- e.g. pulled out of an uploaded recording
    source     TEXT NOT NULL DEFAULT 'onboarding' CHECK (source IN ('onboarding','post_session','manual')),
    inferred   JSONB NOT NULL DEFAULT '{}'::jsonb,          -- {domain, skill_ids[], confidence, why[]}
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS failed_questions_user_idx ON failed_questions (user_id, created_at DESC);

-- =====================================================================================
-- 2. TAXONOMY  (skill circles: domain -> skills; the skill graph slice)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS domains (
    id       TEXT PRIMARY KEY,                              -- 'hw' | 'infra' | 'sw' | 'other'
    name     TEXT NOT NULL,
    tagline  TEXT,
    position INT  NOT NULL DEFAULT 0
);

-- One row per wedge. "Something else" topics create a user-scoped skill under domain 'other'.
CREATE TABLE IF NOT EXISTS skills (
    id            TEXT PRIMARY KEY,                         -- 'infra.reverse_proxy'
    domain_id     TEXT NOT NULL REFERENCES domains(id),
    name          TEXT NOT NULL,
    description   TEXT,
    position      INT  NOT NULL DEFAULT 0,
    generated_for TEXT REFERENCES users(id) ON DELETE CASCADE,   -- NULL = shared canon
    merged_into   TEXT REFERENCES skills(id),               -- a custom topic found to duplicate an existing skill
    active        BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS skills_domain_idx ON skills (domain_id, position);

CREATE TABLE IF NOT EXISTS skill_edges (
    from_skill TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    to_skill   TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL DEFAULT 'prereq' CHECK (kind IN ('prereq','related')),
    PRIMARY KEY (from_skill, to_skill, kind),
    CHECK (from_skill <> to_skill)
);

-- The dark tick on each wedge: what a company expects. role '*' = any role.
CREATE TABLE IF NOT EXISTS skill_targets (
    company  TEXT NOT NULL,
    role     TEXT NOT NULL DEFAULT '*',
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    level    SMALLINT NOT NULL CHECK (level BETWEEN 0 AND 100),
    source   TEXT NOT NULL DEFAULT 'curated' CHECK (source IN ('curated','generated')),
    PRIMARY KEY (company, role, skill_id)
);

-- =====================================================================================
-- 3. ENGINES AND TRACK TEMPLATES  (what can be run, and how it is generated)
-- =====================================================================================
-- layer 1 = hand-built simulator, 2 = model fills a validated template, 3 = conceptual drill.
CREATE TABLE IF NOT EXISTS engines (
    id          TEXT PRIMARY KEY,                           -- 'linux_fault', 'dc_solver', 'c_grader', ...
    name        TEXT NOT NULL,
    layer       SMALLINT NOT NULL CHECK (layer IN (1,2,3)),
    version     TEXT NOT NULL DEFAULT '1',
    param_schema JSONB NOT NULL DEFAULT '{}'::jsonb,        -- JSON Schema the generator must satisfy
    spec_schema  JSONB NOT NULL DEFAULT '{}'::jsonb,        -- JSON Schema of a finished scenario spec
    validator   TEXT,                                       -- name of the deterministic check ('solver_reproduces_symptom')
    surfaces    TEXT[] NOT NULL DEFAULT '{voice}',          -- UI the session needs: voice, terminal, editor, schematic, whiteboard, browser, pi3d
    event_kinds TEXT[] NOT NULL DEFAULT '{turn}',           -- kinds this engine writes to session_events (documentation + evaluator input)
    evaluators  TEXT[] NOT NULL DEFAULT '{process,technical,hypothesis,communication}',  -- the fleet that grades this engine's sessions
    enabled     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS track_templates (
    id             TEXT PRIMARY KEY,
    domain_id      TEXT NOT NULL REFERENCES domains(id),
    engine_id      TEXT NOT NULL REFERENCES engines(id),
    title          TEXT NOT NULL,
    description    TEXT,
    interview_type TEXT,                                    -- 'debug', 'read_code', 'write_code', 'design', ...
    difficulty     SMALLINT NOT NULL DEFAULT 2 CHECK (difficulty BETWEEN 1 AND 5),
    params_default JSONB NOT NULL DEFAULT '{}'::jsonb,
    position       INT NOT NULL DEFAULT 0,
    active         BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS template_skills (
    template_id TEXT NOT NULL REFERENCES track_templates(id) ON DELETE CASCADE,
    skill_id    TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    weight      REAL NOT NULL DEFAULT 1 CHECK (weight > 0),
    PRIMARY KEY (template_id, skill_id)
);

-- =====================================================================================
-- 4. GENERATION AUDIT AND CACHE  (every model call that produces content)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS generation_jobs (
    id             TEXT PRIMARY KEY,
    user_id        TEXT REFERENCES users(id) ON DELETE SET NULL,
    kind           TEXT NOT NULL,                           -- plan, track, scenario, step_set, lesson, opener, whiteboard_critique, evaluator, claim_regen, extract_source
    subject_type   TEXT,                                    -- 'plan' | 'track' | 'scenario' | 'session' | ...
    subject_id     TEXT,
    status         TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed','cached')),
    parent_job_id  TEXT REFERENCES generation_jobs(id) ON DELETE SET NULL,   -- pipeline: generate -> validate -> second-model check -> regenerate
    stage          TEXT,                                    -- feeds the "Composing..." lines
    model          TEXT,
    prompt_version TEXT,
    cache_key      TEXT,                                    -- hash(kind, prompt_version, normalized inputs)
    is_seed        BOOLEAN NOT NULL DEFAULT FALSE,          -- pre-generated demo fallback, served if live generation fails
    request        JSONB NOT NULL DEFAULT '{}'::jsonb,
    response       JSONB,
    schema_ok      BOOLEAN,                                 -- output passed JSON Schema validation
    error          TEXT,
    attempt        SMALLINT NOT NULL DEFAULT 1,
    tokens_in      INT,
    tokens_out     INT,
    latency_ms     INT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS gen_jobs_cache_idx ON generation_jobs (cache_key, is_seed DESC, created_at DESC)
    WHERE status IN ('succeeded','cached');
CREATE INDEX IF NOT EXISTS gen_jobs_subject_idx ON generation_jobs (subject_type, subject_id);

-- =====================================================================================
-- 5. PLANS, TRACKS, SCENARIOS  (home screen: tabs, circles, track cards)
-- =====================================================================================
-- Editing answers creates a new version; the old one is superseded, never mutated.
CREATE TABLE IF NOT EXISTS plans (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version        INT  NOT NULL DEFAULT 1,
    inputs         JSONB NOT NULL DEFAULT '{}'::jsonb,      -- snapshot of profile + failed question used
    inference      JSONB NOT NULL DEFAULT '{}'::jsonb,      -- {scores:{hw,infra,sw}, why:{...}}
    primary_domain TEXT REFERENCES domains(id),             -- the tab marked Recommended
    status         TEXT NOT NULL DEFAULT 'composing' CHECK (status IN ('composing','ready','failed','superseded')),
    job_id         TEXT REFERENCES generation_jobs(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, version)
);

-- A track is what the user sees as a card. Templates are the catalog; tracks are per-user instances.
CREATE TABLE IF NOT EXISTS tracks (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id     TEXT REFERENCES plans(id) ON DELETE SET NULL,
    template_id TEXT REFERENCES track_templates(id),        -- NULL for custom "something else" topics
    domain_id   TEXT NOT NULL REFERENCES domains(id),
    engine_id   TEXT NOT NULL REFERENCES engines(id),
    layer       SMALLINT NOT NULL CHECK (layer IN (1,2,3)),
    kind        TEXT NOT NULL DEFAULT 'drill' CHECK (kind IN ('drill','loop')),   -- 'loop' = a mock interview made of child tracks
    parent_track_id TEXT REFERENCES tracks(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    summary     TEXT,
    source      TEXT NOT NULL CHECK (source IN ('onboarding','failed_question','retest','custom_topic','catalog')),
    source_ref  TEXT,                                       -- failed_questions.id, source_documents.id or retest_queue.id
    reason      TEXT,                                       -- the tag on the card: "Because you skipped the throttle flags"
    status      TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','generating','ready','failed','archived')),
    in_plan     BOOLEAN NOT NULL DEFAULT FALSE,             -- "Add to my plan"
    recommended BOOLEAN NOT NULL DEFAULT FALSE,             -- the "Start here" banner
    position    INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tracks_user_idx ON tracks (user_id, domain_id, position) WHERE status <> 'archived';
CREATE TABLE IF NOT EXISTS track_skills (
    track_id TEXT NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    weight   REAL NOT NULL DEFAULT 1 CHECK (weight > 0),
    PRIMARY KEY (track_id, skill_id)
);

-- Verified building blocks that generation adapts instead of inventing: LeetCode-style problems, C snippets with a
-- known bug, netlist bases, behavioral prompts, system-design prompts. Layer 2 starts from one of these.
CREATE TABLE IF NOT EXISTS content_items (
    id         TEXT PRIMARY KEY,
    engine_id  TEXT NOT NULL REFERENCES engines(id),
    kind       TEXT NOT NULL,                               -- 'problem','snippet','netlist','prompt','repo_template'
    title      TEXT NOT NULL,
    body       JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags       TEXT[] NOT NULL DEFAULT '{}',
    difficulty SMALLINT CHECK (difficulty BETWEEN 1 AND 5),
    verified   BOOLEAN NOT NULL DEFAULT FALSE,              -- reference solution or fault checked by the engine's validator
    source     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS content_items_lookup_idx ON content_items (engine_id, kind, difficulty) WHERE verified;
CREATE TABLE IF NOT EXISTS content_skills (
    content_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    skill_id   TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (content_id, skill_id)
);

-- A concrete, runnable instance: the netlist with 2 planted faults, the C snippet, the conceptual drill steps.
-- A track is only 'ready' once a scenario has validity = 'passed' (enforced by the service, see v_track_ready).
CREATE TABLE IF NOT EXISTS scenarios (
    id             TEXT PRIMARY KEY,
    track_id       TEXT NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    engine_id      TEXT NOT NULL REFERENCES engines(id),
    engine_version TEXT NOT NULL,
    params         JSONB NOT NULL DEFAULT '{}'::jsonb,     -- what the generator chose (faults, values, difficulty)
    params_hash    TEXT,
    seed           BIGINT,                                  -- makes engine runs reproducible
    spec           JSONB NOT NULL DEFAULT '{}'::jsonb,      -- engine payload: netlist, schematic, snippet, steps
    rubric         JSONB NOT NULL DEFAULT '[]'::jsonb,      -- [{id, text, skill_id, weight}] fed to evaluators
    content_item_id TEXT REFERENCES content_items(id),     -- the verified base this was adapted from, if any
    variant_of     TEXT REFERENCES scenarios(id),           -- retests: same stack, different fault
    validity       TEXT NOT NULL DEFAULT 'pending' CHECK (validity IN ('pending','passed','failed')),
    validity_report JSONB NOT NULL DEFAULT '{}'::jsonb,     -- "solver reproduces 4.63 V at the board"
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    job_id         TEXT REFERENCES generation_jobs(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS scenarios_track_idx ON scenarios (track_id, created_at DESC);
CREATE INDEX IF NOT EXISTS scenarios_hash_idx ON scenarios (engine_id, params_hash);

-- The stepper, the hints and the "what counts as done" for each stage. Evaluators read these to know what to look for.
CREATE TABLE IF NOT EXISTS scenario_steps (
    scenario_id TEXT NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    idx         SMALLINT NOT NULL,
    title       TEXT NOT NULL,
    surface     TEXT NOT NULL DEFAULT 'voice',              -- what this step is done on: voice, star, whiteboard, terminal, editor, schematic, pi3d
    config      JSONB NOT NULL DEFAULT '{}'::jsonb,         -- surface options: {whiteboard_prompt, min_items} | {star:true, need:['result']}
    task        TEXT NOT NULL,                              -- "Your turn" text
    hints       TEXT[] NOT NULL DEFAULT '{}',               -- escalating
    success     JSONB NOT NULL DEFAULT '{}'::jsonb,         -- engine-checkable completion condition
    rubric_ids  TEXT[] NOT NULL DEFAULT '{}',               -- scenarios.rubric ids this step exercises
    PRIMARY KEY (scenario_id, idx)
);

-- =====================================================================================
-- 6. SESSIONS  (the interview itself)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS sessions (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_id          TEXT NOT NULL REFERENCES tracks(id),
    scenario_id       TEXT NOT NULL REFERENCES scenarios(id),
    kind              TEXT NOT NULL DEFAULT 'run' CHECK (kind IN ('run','retest')),
    parent_session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,  -- the session a retest follows up
    status            TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created','live','ended','grading','graded','failed')),
    step              SMALLINT NOT NULL DEFAULT 0,
    engine_state      JSONB NOT NULL DEFAULT '{}'::jsonb,   -- snapshot so a reload resumes mid-scenario
    consent           JSONB NOT NULL DEFAULT '{"transcript":true,"audio":false}'::jsonb,
    whiteboard_mode   TEXT NOT NULL DEFAULT 'inline' CHECK (whiteboard_mode IN ('inline','linked')),   -- on this screen, or on a paired iPad
    started_at        TIMESTAMPTZ,
    ended_at          TIMESTAMPTZ,
    graded_at         TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions (user_id, created_at DESC);

-- iPad whiteboard, Pi kiosk, phone. A device pairs to a session by short code or QR. The code is single use and expires.
CREATE TABLE IF NOT EXISTS session_devices (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('ipad_whiteboard','pi_kiosk','phone')),
    pair_code    TEXT UNIQUE,                               -- 'PC-Q8YP', shown as text and encoded in the QR
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','connected','disconnected','expired')),
    input_kind   TEXT CHECK (input_kind IN ('pencil','touch','mouse')),
    expires_at   TIMESTAMPTZ,
    paired_at    TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS session_devices_session_idx ON session_devices (session_id, kind);

-- Which skills a retest is meant to move.
CREATE TABLE IF NOT EXISTS session_focus (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    skill_id   TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    reason     TEXT,
    PRIMARY KEY (session_id, skill_id)
);

-- Calibrates generation: too easy / too hard / not relevant. Read by the next plan and the next scenario's difficulty.
CREATE TABLE IF NOT EXISTS track_feedback (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_id   TEXT NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    rating     TEXT NOT NULL CHECK (rating IN ('too_easy','too_hard','not_relevant','great')),
    note       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Whiteboards, drawn schematics, code snapshots. Large blobs live in object storage (blob_key).
CREATE TABLE IF NOT EXISTS artifacts (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,                             -- schematic, whiteboard, code_snapshot, netlist_attempt, star_answer, ...
    step         SMALLINT,
    version      INT NOT NULL DEFAULT 1,                    -- a board is snapshotted at the end of its step, and again if the user reopens it
    device_id    TEXT REFERENCES session_devices(id) ON DELETE SET NULL,   -- which device drew it (NULL = on screen)
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,        -- whiteboard: {canvas:{w,h}, items:[candidate vector shapes and decimated paths]}. Interviewer marks are NOT here: see board_annotations
    blob_key     TEXT,                                      -- PNG of the candidate's own strokes only, sent to the vision model
    annotated_blob_key TEXT,                                -- PNG with the interviewer's marks composited on top (the thumbnail shown afterwards)
    critique_job_id TEXT REFERENCES generation_jobs(id) ON DELETE SET NULL,   -- the whiteboard_critique call that read this snapshot
    check_result JSONB,                                     -- candidate netlist vs reference, or vision critique
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS artifacts_session_idx ON artifacts (session_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS artifacts_version_idx ON artifacts (session_id, kind, COALESCE(step, -1), version);

-- Whiteboard turn-taking (set per step in scenario_steps.config):
--   {"mode":"talk_while_drawing","look":"on_done"|"on_pause","annotate":true,"max_marks":4}
-- The candidate draws and talks. Questions to the interviewer are answered at once and briefly. When the candidate
-- presses Done (or pauses, if look = on_pause) the system snapshots the board, sends the PNG, the spoken transcript
-- and the stroke log to the vision model (generation_jobs.kind = 'whiteboard_critique'), and the result comes back as
-- structured marks plus the line Dana says with each. The client replays them in order.
-- Marks are stored apart from the candidate's strokes so a critique can never be mistaken for, or graded as, the
-- candidate's own work, and so a retest can re-render a board with or without them.
CREATE TABLE IF NOT EXISTS board_annotations (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    artifact_id   TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,   -- the board snapshot version this mark was drawn on
    author        TEXT NOT NULL DEFAULT 'interviewer' CHECK (author IN ('interviewer','candidate_reply')),
    kind          TEXT NOT NULL CHECK (kind IN ('circle','arrow','underline','highlight','sticky','cross','check')),
    geometry      JSONB NOT NULL,                           -- canvas coords, same 900x540 space as the board: {cx,cy,rx,ry} | {x1,y1,x2,y2} | {x,y,w,h}
    text          TEXT,                                     -- sticky note text, or a short label
    severity      TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('good','info','probe','problem')),   -- good = praise, probe = a question, problem = a gap
    target_seq    BIGINT,                                   -- session_events.seq of the candidate stroke it points at (soft ref, see header)
    speech        TEXT,                                     -- what Dana says while drawing this mark; also written as a turn event
    event_seq     BIGINT,                                   -- session_events.seq of the 'annotation' event written when it was drawn
    order_idx     SMALLINT NOT NULL,                        -- replay order
    draw_ms       INT NOT NULL DEFAULT 700,                 -- how long the stroke animates, so replays feel the same
    source_job_id TEXT REFERENCES generation_jobs(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sticky_has_text CHECK (kind <> 'sticky' OR text IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS board_annotations_order_idx ON board_annotations (artifact_id, order_idx);
CREATE INDEX IF NOT EXISTS board_annotations_session_idx ON board_annotations (session_id);

-- =====================================================================================
-- 7. SESSION EVENTS  (hypertable: the evidence log every claim must point at)
-- =====================================================================================
-- Commands, file edits, probe readings, schematic edits, part drops, hints and every spoken turn.
-- payload examples:
--   stroke    {k:'rect'|'arrow'|'text'|'path', label, n, bbox, device:'screen'|'ipad'}   (whiteboard; full vector lives in artifacts)
--   turn      {text, q, board:true, items_so_far}   spoken or typed while drawing; q = it was a question to the interviewer
--   note      {board_snapshot:true, items, sent_to:'vision', bytes, transcript_turns}   the moment the interviewer 'looks' at the board
--   annotation {annotation_id, k, text, seg, target_seq}   actor=interviewer: one mark Dana drew (circle, arrow, note); target_seq = the candidate stroke it points at
--   analysis  {star:{s,t,a,r}, turn_seq}        live STAR detection while the user speaks (system actor, a fast model call)
--   command   {cmd, exit, out_head}            probe   {node, reading, expected, fault_hit}
--   turn      {role, text, interrupted}         edit    {file, diff}
--   part_drop {part, accepted, feedback}        hint    {level}
CREATE TABLE IF NOT EXISTS session_events (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
    seq        BIGINT GENERATED ALWAYS AS IDENTITY,         -- stable evidence reference, ordered per session
    kind       TEXT NOT NULL,                               -- open vocabulary, declared per engine in engines.event_kinds:
                                                            -- command, edit, probe, schematic_edit, part_drop, hint, step, turn, note, run_tests, stroke, ...
    actor      TEXT NOT NULL DEFAULT 'candidate' CHECK (actor IN ('candidate','interviewer','system')),
    step       SMALLINT,
    payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (session_id, ts, seq)
);
SELECT create_hypertable('session_events', 'ts', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS session_events_seq_idx ON session_events (session_id, seq);
CREATE INDEX IF NOT EXISTS session_events_kind_idx ON session_events (session_id, kind, ts);
-- Compression and retention: skip for the hackathon. Deleting from compressed chunks needs TimescaleDB 2.11+.
-- ALTER TABLE session_events SET (timescaledb.compress, timescaledb.compress_segmentby = 'session_id');
-- SELECT add_compression_policy('session_events', INTERVAL '30 days', if_not_exists => TRUE);

-- =====================================================================================
-- 8. GRADING  (evaluator fleet -> claims -> evidence checker -> report)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS evaluator_runs (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    evaluator   TEXT NOT NULL,                              -- from engines.evaluators: process, technical, hypothesis, communication, whiteboard, star_structure, ...
    attempt     SMALLINT NOT NULL DEFAULT 1,
    status      TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','done','failed')),
    model       TEXT,
    prompt_version TEXT,
    score       SMALLINT CHECK (score BETWEEN 0 AND 100),
    summary     TEXT,
    output      JSONB,                                      -- raw schema-valid output
    schema_ok   BOOLEAN,
    error       TEXT,
    job_id      TEXT REFERENCES generation_jobs(id),
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    latency_ms  INT,
    UNIQUE (session_id, evaluator, attempt)
);

-- One claim = one statement about the candidate with the events that prove it.
CREATE TABLE IF NOT EXISTS claims (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES evaluator_runs(id) ON DELETE CASCADE,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    skill_id      TEXT REFERENCES skills(id),
    rubric_id     TEXT,                                     -- scenarios.rubric[].id this claim speaks to
    text          TEXT NOT NULL,
    polarity      TEXT NOT NULL CHECK (polarity IN ('strength','gap','neutral')),
    evidence_seq  BIGINT[] NOT NULL DEFAULT '{}',           -- session_events.seq values (soft reference)
    check_status  TEXT NOT NULL DEFAULT 'pending' CHECK (check_status IN ('pending','verified','rejected')),
    check_reason  TEXT,                                     -- "no matching transcript turn"
    supersedes_id TEXT REFERENCES claims(id),               -- the regenerated replacement of a rejected claim
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The invariant: nothing is verified without evidence.
    CONSTRAINT claims_verified_has_evidence CHECK (check_status <> 'verified' OR cardinality(evidence_seq) > 0)
);
CREATE INDEX IF NOT EXISTS claims_session_idx ON claims (session_id, check_status);
CREATE INDEX IF NOT EXISTS claims_skill_idx ON claims (skill_id) WHERE check_status = 'verified';

-- The merged result shown on the grading screen. Only verified claims are included.
CREATE TABLE IF NOT EXISTS session_reports (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    overall    SMALLINT CHECK (overall BETWEEN 0 AND 100),
    report     JSONB NOT NULL DEFAULT '{}'::jsonb,
    stats      JSONB NOT NULL DEFAULT '{}'::jsonb,          -- {evaluators, claims, rejected, regenerated, wall_ms}
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================================
-- 9. MASTERY  (skill circles and the mastery chart)
-- =====================================================================================
-- Append-only history. The service blends old and new and inserts the final score.
CREATE TABLE IF NOT EXISTS skill_assessments (
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id    TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    score       SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 100),
    confidence  REAL CHECK (confidence BETWEEN 0 AND 1),
    source      TEXT NOT NULL CHECK (source IN ('intake_estimate','session','retest','self_report')),
    is_estimate BOOLEAN NOT NULL DEFAULT FALSE,             -- drawn lighter on the circle
    session_id  TEXT,                                       -- soft ref: kept, anonymized, if the session is deleted
    claim_ids   TEXT[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (user_id, skill_id, ts)
);
SELECT create_hypertable('skill_assessments', 'ts', chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS skill_assessments_session_idx ON skill_assessments (session_id) WHERE session_id IS NOT NULL;

-- Current state: one row per wedge per user. This is what the circle reads. Mirrors the latest assessment.
CREATE TABLE IF NOT EXISTS user_skills (
    user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id         TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    score            SMALLINT CHECK (score BETWEEN 0 AND 100),   -- NULL = not assessed (dashed wedge)
    target           SMALLINT NOT NULL DEFAULT 70 CHECK (target BETWEEN 0 AND 100),
    is_estimate      BOOLEAN NOT NULL DEFAULT FALSE,
    trend            SMALLINT,                                   -- last change
    last_assessed_at TIMESTAMPTZ,
    PRIMARY KEY (user_id, skill_id)
);
CREATE INDEX IF NOT EXISTS user_skills_user_idx ON user_skills (user_id);

CREATE OR REPLACE FUNCTION apply_assessment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO user_skills (user_id, skill_id, score, is_estimate, last_assessed_at)
    VALUES (NEW.user_id, NEW.skill_id, NEW.score, NEW.is_estimate, NEW.ts)
    ON CONFLICT (user_id, skill_id) DO UPDATE
       SET trend = NEW.score - COALESCE(user_skills.score, NEW.score),
           score = NEW.score,
           is_estimate = NEW.is_estimate,
           last_assessed_at = NEW.ts;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS skill_assessments_apply ON skill_assessments;
CREATE TRIGGER skill_assessments_apply AFTER INSERT ON skill_assessments
    FOR EACH ROW EXECUTE FUNCTION apply_assessment();

-- =====================================================================================
-- 10. LOOP: GAP -> LESSON -> RETEST, AND IMPLICIT MEMORY
-- =====================================================================================
CREATE TABLE IF NOT EXISTS lessons (
    id           TEXT PRIMARY KEY,
    skill_id     TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    user_id      TEXT REFERENCES users(id) ON DELETE CASCADE,    -- NULL = shared canned lesson
    claim_id     TEXT REFERENCES claims(id) ON DELETE SET NULL,  -- the gap that triggered it
    body         TEXT NOT NULL,
    ai_generated BOOLEAN NOT NULL DEFAULT TRUE,
    job_id       TEXT REFERENCES generation_jobs(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS lessons_lookup_idx ON lessons (skill_id, user_id, created_at DESC);

-- What to offer next. A queued row becomes the highlighted retest card, with `reason` as its tag.
CREATE TABLE IF NOT EXISTS retest_queue (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id    TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    session_id  TEXT REFERENCES sessions(id) ON DELETE SET NULL,   -- where the gap was found
    claim_id    TEXT REFERENCES claims(id) ON DELETE SET NULL,
    reason      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','offered','taken','dismissed')),
    track_id    TEXT REFERENCES tracks(id) ON DELETE SET NULL,     -- set once the retest scenario is generated
    due_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS retest_queue_user_idx ON retest_queue (user_id, status, due_at);

-- Long-term memory. Written from verified claims, read by the opener, retest tags and plan inference.
-- backend = 'backboard' rows keep only the pointer; the text stays for local fallback and for deletion.
CREATE TABLE IF NOT EXISTS memories (
    id                TEXT PRIMARY KEY,
    owner_id          TEXT NOT NULL,
    text              TEXT NOT NULL,
    kind              TEXT NOT NULL DEFAULT 'fact' CHECK (kind IN ('habit','strength','gap','preference','fact')),
    skill_id          TEXT REFERENCES skills(id) ON DELETE SET NULL,
    source_session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    source_claim_id   TEXT REFERENCES claims(id) ON DELETE SET NULL,
    salience          REAL NOT NULL DEFAULT 0.5 CHECK (salience BETWEEN 0 AND 1),
    backend           TEXT NOT NULL DEFAULT 'postgres' CHECK (backend IN ('postgres','backboard')),
    external_id       TEXT,                                 -- Backboard memory id
    data              JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_used_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS memories_owner_idx ON memories (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS memories_recall_idx ON memories (owner_id, kind, salience DESC);
-- ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding vector(768);   -- only with pgvector

-- Behavioral: the user's story bank. Stories are written from resume projects and from sessions,
-- and mapped to the questions they answer, so a retest can ask for a different story.
CREATE TABLE IF NOT EXISTS star_stories (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    situation  TEXT, task TEXT, action TEXT, result TEXT,
    metrics    TEXT[] NOT NULL DEFAULT '{}',                -- quantified results, e.g. '45 -> 12 min builds'
    tags       TEXT[] NOT NULL DEFAULT '{}',                -- competencies: ownership, conflict, deadline, ...
    skill_ids  TEXT[] NOT NULL DEFAULT '{}',
    source_doc_id TEXT REFERENCES source_documents(id) ON DELETE SET NULL,
    source_session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS session_stories (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    story_id   TEXT NOT NULL REFERENCES star_stories(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('told','suggested')),
    PRIMARY KEY (session_id, story_id)
);

-- =====================================================================================
-- 11. METRICS  (hypertable: latency readout, "time to load your site", anything measured)
-- =====================================================================================
-- name examples: stt_ms, llm_first_token_ms, tts_first_byte_ms, turn_e2e_ms, eval_ms, scenario.ttfb_ms
-- Measured values only. Nothing is ever back-filled with an estimate.
CREATE TABLE IF NOT EXISTS metrics (
    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    user_id    TEXT,
    ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
    name       TEXT NOT NULL,
    value      DOUBLE PRECISION NOT NULL,
    step       SMALLINT,
    label      TEXT,                                        -- chart x label: '502', 'Proxy', 'Disk', 'Power'
    data       JSONB NOT NULL DEFAULT '{}'::jsonb
);
SELECT create_hypertable('metrics', 'ts', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS metrics_session_idx ON metrics (session_id, name, ts DESC);

-- =====================================================================================
-- 12. CONSENT AND DELETION
-- =====================================================================================
-- Removes content for one session and returns the row count (the API reports it).
-- Skill assessments are kept but unlinked, so a user's circle does not silently shrink.
CREATE OR REPLACE FUNCTION delete_session(p_id TEXT) RETURNS INT LANGUAGE plpgsql AS $$
DECLARE n INT := 0; c INT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM sessions WHERE id = p_id) THEN RETURN NULL; END IF;
    DELETE FROM session_events WHERE session_id = p_id;  GET DIAGNOSTICS c = ROW_COUNT; n := n + c;
    DELETE FROM metrics        WHERE session_id = p_id;  GET DIAGNOSTICS c = ROW_COUNT; n := n + c;
    DELETE FROM memories       WHERE source_session_id = p_id; GET DIAGNOSTICS c = ROW_COUNT; n := n + c;
    UPDATE skill_assessments SET session_id = NULL, claim_ids = '{}' WHERE session_id = p_id;
    SELECT n + count(*) INTO n FROM claims WHERE session_id = p_id;
    SELECT n + count(*) INTO n FROM evaluator_runs WHERE session_id = p_id;
    SELECT n + count(*) INTO n FROM artifacts WHERE session_id = p_id;
    DELETE FROM sessions WHERE id = p_id;                -- cascades runs, claims, reports, artifacts, annotations, devices
    RETURN n + 1;
END $$;

-- =====================================================================================
-- 13. VIEWS  (what the screens read)
-- =====================================================================================
-- One row per wedge, with the skill name and domain. Untested wedges appear with score NULL.
CREATE OR REPLACE VIEW v_skill_circle AS
SELECT us.user_id, s.domain_id, s.id AS skill_id, s.name, s.position,
       us.score, us.target, us.is_estimate, us.trend, us.last_assessed_at,
       CASE WHEN us.score IS NULL THEN 'none'
            WHEN us.score < us.target - 25 THEN 'gap' ELSE 'ok' END AS state
FROM user_skills us JOIN skills s ON s.id = us.skill_id AND s.active;

-- Tab badge and circle centre: the average of assessed wedges.
CREATE OR REPLACE VIEW v_domain_circle AS
SELECT user_id, domain_id,
       round(avg(score))::int AS average,
       count(score) AS assessed, count(*) AS total
FROM v_skill_circle GROUP BY user_id, domain_id;

-- A track card may be started only when a validated scenario exists.
CREATE OR REPLACE VIEW v_track_ready AS
SELECT t.*, sc.id AS scenario_id
FROM tracks t
JOIN LATERAL (SELECT id FROM scenarios
              WHERE track_id = t.id AND validity = 'passed' AND is_active
              ORDER BY created_at DESC LIMIT 1) sc ON TRUE;

-- Biggest-gap line under the circle.
CREATE OR REPLACE VIEW v_biggest_gap AS
SELECT DISTINCT ON (user_id, domain_id) user_id, domain_id, skill_id, name, score, target
FROM v_skill_circle WHERE score IS NOT NULL
ORDER BY user_id, domain_id, (score - target);

-- Interviewer opener input: recent habits and gaps, most salient first.
CREATE OR REPLACE VIEW v_opener_memory AS
SELECT owner_id, id, kind, text, skill_id, salience, created_at,
       row_number() OVER (PARTITION BY owner_id ORDER BY salience DESC, created_at DESC) AS rank
FROM memories WHERE kind IN ('habit','gap','strength');

-- Per-session latency readout (p50/p95 from raw rows; one session is small).
CREATE OR REPLACE VIEW v_board_replay AS
SELECT a.session_id, a.id AS artifact_id, a.version, b.order_idx, b.kind, b.geometry, b.text, b.severity,
       b.speech, b.draw_ms, b.target_seq, b.event_seq
FROM artifacts a JOIN board_annotations b ON b.artifact_id = a.id
WHERE a.kind = 'whiteboard';

CREATE OR REPLACE VIEW v_session_latency AS
SELECT session_id, name, count(*) AS n,
       percentile_cont(0.5)  WITHIN GROUP (ORDER BY value) AS p50,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY value) AS p95,
       max(value) AS max
FROM metrics WHERE name LIKE '%\_ms' ESCAPE '\' GROUP BY session_id, name;

-- =====================================================================================
-- 14. CONTINUOUS AGGREGATES  (Tiger Data; the mastery chart and the live latency footer)
-- =====================================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mastery_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT user_id, skill_id,
       time_bucket(INTERVAL '1 hour', ts) AS bucket,
       last(score, ts)  AS score,
       max(score)       AS best,
       count(*)         AS samples
FROM skill_assessments
WHERE NOT is_estimate
GROUP BY user_id, skill_id, time_bucket(INTERVAL '1 hour', ts)
WITH NO DATA;
SELECT add_continuous_aggregate_policy('mastery_hourly',
    start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute', if_not_exists => TRUE);

CREATE MATERIALIZED VIEW IF NOT EXISTS latency_1m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT name, time_bucket(INTERVAL '1 minute', ts) AS bucket,
       count(*) AS n, avg(value) AS avg, min(value) AS min, max(value) AS max
FROM metrics
WHERE name LIKE '%\_ms' ESCAPE '\'
GROUP BY name, time_bucket(INTERVAL '1 minute', ts)
WITH NO DATA;
SELECT add_continuous_aggregate_policy('latency_1m',
    start_offset => INTERVAL '1 day', end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute', if_not_exists => TRUE);

-- =====================================================================================
-- 15. SEED  (the catalog from the mockup; extend freely)
-- =====================================================================================
INSERT INTO domains (id, name, tagline, position) VALUES
 ('hw','Hardware','Circuits and embedded C',1), ('infra','Infra','Linux, servers and networking',2),
 ('sw','Software','Web dev and algorithms',3),  ('comm','Communication','Behavioral stories and explaining your work',4),
 ('other','Other','Topics you add',5)
ON CONFLICT DO NOTHING;

INSERT INTO skills (id, domain_id, name, position) VALUES
 ('infra.linux_shell','infra','Linux & shell',1), ('infra.services','infra','Services',2), ('infra.networking','infra','Networking',3),
 ('infra.reverse_proxy','infra','Reverse proxy',4), ('infra.permissions','infra','Permissions',5), ('infra.disk_logs','infra','Disk & logs',6),
 ('infra.power_thermals','infra','Power & thermals',7), ('infra.debug_method','infra','Debug method',8),
 ('hw.circuit_probing','hw','Circuit probing',1), ('hw.power_rails','hw','Power rails',2), ('hw.c_read_debug','hw','C: read & debug',3),
 ('hw.c_bitops_drivers','hw','C: bit ops & drivers',4), ('hw.datasheets','hw','Datasheets',5),
 ('sw.debug_feature','sw','Debug a feature',1), ('sw.build_endpoint','sw','Build an endpoint',2), ('sw.algorithms','sw','Algorithms',3),
 ('sw.explain_coding','sw','Explain while coding',4), ('sw.system_design','sw','System design',5),
 ('comm.star_structure','comm','STAR structure',1), ('comm.ownership','comm','Ownership',2), ('comm.quantifying_impact','comm','Quantifying impact',3),
 ('comm.followups','comm','Handling follow-ups',4), ('comm.conflict_feedback','comm','Conflict & feedback',5)
ON CONFLICT DO NOTHING;

INSERT INTO skill_edges (from_skill, to_skill) VALUES
 ('infra.linux_shell','infra.services'), ('infra.services','infra.reverse_proxy'), ('infra.linux_shell','infra.permissions'),
 ('infra.linux_shell','infra.disk_logs'), ('hw.power_rails','hw.circuit_probing'), ('infra.disk_logs','infra.power_thermals')
ON CONFLICT DO NOTHING;

INSERT INTO skill_targets (company, role, skill_id, level) VALUES
 ('NVIDIA','*','hw.circuit_probing',72), ('NVIDIA','*','hw.c_bitops_drivers',80), ('NVIDIA','*','hw.c_read_debug',78),
 ('Tesla','*','hw.power_rails',75), ('Tesla','*','infra.debug_method',80), ('*','*','infra.reverse_proxy',75)
ON CONFLICT DO NOTHING;

INSERT INTO engines (id, name, layer, validator, surfaces, event_kinds, evaluators) VALUES
 ('linux_fault','Linux fault engine',1,'every_fault_reproduces_symptom','{voice,terminal,editor,browser,pi3d}','{command,edit,part_drop,hint,step,turn}','{process,technical,hypothesis,communication}'),
 ('dc_solver','DC circuit solver',1,'solver_reproduces_symptom','{voice,schematic,whiteboard}','{probe,schematic_edit,hint,step,turn}','{process,technical,hypothesis,communication}'),
 ('net_sim','Network path simulator',2,'latency_profile_reproduces','{voice,terminal}','{command,hint,step,turn}','{process,technical,hypothesis,communication}'),
 ('c_grader','C review and write grader',2,'compiler_and_race_harness','{voice,editor}','{edit,run_tests,hint,step,turn}','{technical,hypothesis,communication}'),
 ('web_repo','Sandboxed web repo',2,'test_fails_then_passes_on_reference','{voice,editor,terminal,browser}','{command,edit,run_tests,hint,step,turn}','{process,technical,hypothesis,communication}'),
 ('conceptual','Conceptual drill',3,'second_model_rubric_check','{voice,whiteboard}','{turn,stroke,note,hint,step}','{requirements,whiteboard,tradeoffs,communication}'),
 ('behavioral','Behavioral and STAR',3,'second_model_rubric_check','{voice,star}','{turn,analysis,hint,step}','{star_structure,ownership,communication}')
ON CONFLICT DO NOTHING;

INSERT INTO track_templates (id, domain_id, engine_id, title, description, interview_type, position) VALUES
 ('infra.pi_site','infra','linux_fault','Fix the site on the Pi','Guided: terminal, editor, 3D Raspberry Pi','debug',1),
 ('infra.slow_request','infra','net_sim','Networking: a slow request','Trace DNS, TCP and a proxy hop','debug',2),
 ('hw.circuit_debug','hw','dc_solver','Circuit debugging','Probe a live schematic, find 2 faults','debug',1),
 ('hw.c_read','hw','c_grader','Embedded C: read and debug','Spot the bug in a driver or ISR','read_code',2),
 ('hw.c_write','hw','c_grader','Embedded C: write low-level code','Bit ops, registers, a small driver','write_code',3),
 ('sw.web_fix','sw','web_repo','Web dev: fix a failing feature','A real repo, a failing test','debug',1),
 ('sw.leetcode','sw','conceptual','LeetCode: explain as you solve','Spoken reasoning, graded on method','algorithm',2),
 ('sw.sysdesign','sw','conceptual','System design: whiteboard','Scope it by voice, draw it on the whiteboard, defend it by voice','design',3),
 ('comm.star','comm','behavioral','Behavioral: tell me about a time','Voice with a live STAR guide, then a follow-up','behavioral',1),
 ('comm.conflict','comm','behavioral','Conflict and feedback','A hard conversation with a teammate','behavioral',2),
 ('comm.story_bank','comm','behavioral','Build your story bank','Turn your projects into reusable stories','behavioral',3)
ON CONFLICT DO NOTHING;

INSERT INTO template_skills (template_id, skill_id, weight) VALUES
 ('infra.pi_site','infra.reverse_proxy',1), ('infra.pi_site','infra.permissions',1), ('infra.pi_site','infra.disk_logs',1),
 ('infra.pi_site','infra.power_thermals',1), ('infra.pi_site','infra.debug_method',1.5),
 ('infra.slow_request','infra.networking',1.5), ('hw.circuit_debug','hw.circuit_probing',1.5), ('hw.circuit_debug','hw.power_rails',1),
 ('hw.c_read','hw.c_read_debug',1.5), ('hw.c_write','hw.c_bitops_drivers',1.5), ('sw.web_fix','sw.debug_feature',1.5),
 ('sw.leetcode','sw.algorithms',1), ('sw.leetcode','sw.explain_coding',1), ('sw.sysdesign','sw.system_design',1.5),
 ('comm.star','comm.star_structure',1.5), ('comm.star','comm.ownership',1), ('comm.star','comm.quantifying_impact',1), ('comm.star','comm.followups',1),
 ('comm.conflict','comm.conflict_feedback',1.5), ('comm.story_bank','comm.star_structure',1)
ON CONFLICT DO NOTHING;

-- =====================================================================================
-- 16. TIER 1 (optional; skip if short on time): season tracker and school cohort view
-- =====================================================================================
CREATE TABLE IF NOT EXISTS applications (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company    TEXT NOT NULL,
    role       TEXT,
    stage      TEXT NOT NULL DEFAULT 'applied' CHECK (stage IN ('applied','screen','onsite','offer','rejected','withdrawn')),
    notes      TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cohorts (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, org TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cohort_members (
    cohort_id TEXT NOT NULL REFERENCES cohorts(id) ON DELETE CASCADE,
    user_id   TEXT NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
    role      TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student','instructor')),
    PRIMARY KEY (cohort_id, user_id)
);
-- Cohort view reads only aggregates, never transcripts or events.
CREATE OR REPLACE VIEW v_cohort_skills AS
SELECT cm.cohort_id, s.skill_id, s.domain_id, s.name,
       round(avg(s.score))::int AS avg_score, count(s.score) AS students_assessed
FROM cohort_members cm JOIN v_skill_circle s ON s.user_id = cm.user_id
WHERE cm.role = 'student' GROUP BY cm.cohort_id, s.skill_id, s.domain_id, s.name;