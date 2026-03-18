"""
models.py — SQLite database schema definition.

Centralizes all SQL statements in the project in one place:
CREATE TABLE, CREATE INDEX, INSERT and SELECT. This way database.py does not
contain inline SQL and schema changes are made here.

Table `simulations` — one row per simulation run:
    id, seed, p_infect, vision_human, vision_zombie, strategy,
    n_scientists, n_military, n_politicians, result, duration,
    humans_final, zombies_final, tick_final, timestamp.

Table `events` — key events that occurred during a simulation:
    id, sim_id (FK → simulations), event_type, tick, description.
    Types: 'infection' | 'death' | 'escape' | 'zombie_death' |
           'antidote' | 'alert' | 'outbreak'.

Analysis queries included:
    SELECT_WIN_RATE_BY_STRATEGY  — win rate grouped by strategy.
    SELECT_SENSITIVITY_P_INFECT  — win rate grouped by p_infect buckets.
"""

# ---------------------------------------------------------------------------
# Nombres de tablas
# ---------------------------------------------------------------------------
TABLE_SIMULATIONS = "simulations"
TABLE_EVENTS = "events"

# ---------------------------------------------------------------------------
# DDL — CREATE TABLE statements
# ---------------------------------------------------------------------------

CREATE_SIMULATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS simulations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    seed            INTEGER NOT NULL,
    p_infect        REAL    NOT NULL,
    vision_human    INTEGER NOT NULL,
    vision_zombie   INTEGER NOT NULL,
    strategy        TEXT    NOT NULL,
    n_scientists    INTEGER NOT NULL,
    n_military      INTEGER NOT NULL,
    n_politicians   INTEGER NOT NULL,
    result          TEXT,           -- 'humans_win' | 'zombies_win' | NULL if in progress
    duration        REAL,           -- duration in seconds
    humans_final    INTEGER,        -- living humans at the end
    zombies_final   INTEGER,        -- zombies at the end
    tick_final      INTEGER,        -- tick when it ended
    timestamp       TEXT NOT NULL   -- ISO 8601
);
"""

CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sim_id      INTEGER NOT NULL,
    event_type  TEXT    NOT NULL,   -- 'infection' | 'death' | 'escape' | 'antidote' | etc.
    tick        INTEGER NOT NULL,
    description TEXT    NOT NULL,
    FOREIGN KEY (sim_id) REFERENCES simulations(id) ON DELETE CASCADE
);
"""

# ---------------------------------------------------------------------------
# Indexes for frequent queries
# ---------------------------------------------------------------------------

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_events_sim_id ON events(sim_id);
CREATE INDEX IF NOT EXISTS idx_simulations_seed ON simulations(seed);
CREATE INDEX IF NOT EXISTS idx_simulations_result ON simulations(result);
"""

# ---------------------------------------------------------------------------
# Grouped SQL for initialization
# ---------------------------------------------------------------------------

SCHEMA_SQL: str = "\n".join([
    CREATE_SIMULATIONS_TABLE,
    CREATE_EVENTS_TABLE,
    CREATE_INDEXES,
])

# ---------------------------------------------------------------------------
# Insert queries (parameterized)
# ---------------------------------------------------------------------------

INSERT_SIMULATION = """
INSERT INTO simulations
    (seed, p_infect, vision_human, vision_zombie, strategy,
     n_scientists, n_military, n_politicians, result, duration,
     humans_final, zombies_final, tick_final, timestamp)
VALUES
    (:seed, :p_infect, :vision_human, :vision_zombie, :strategy,
     :n_scientists, :n_military, :n_politicians, :result, :duration,
     :humans_final, :zombies_final, :tick_final, :timestamp);
"""

INSERT_EVENT = """
INSERT INTO events (sim_id, event_type, tick, description)
VALUES (?, ?, ?, ?);
"""

# ---------------------------------------------------------------------------
# Select queries
# ---------------------------------------------------------------------------

SELECT_ALL_SIMULATIONS = """
SELECT * FROM simulations ORDER BY timestamp DESC;
"""

SELECT_SIMULATION_BY_SEED = """
SELECT * FROM simulations WHERE seed = ? ORDER BY timestamp DESC LIMIT 1;
"""

SELECT_EVENTS_BY_SIM = """
SELECT * FROM events WHERE sim_id = ? ORDER BY tick ASC;
"""

SELECT_WIN_RATE_BY_STRATEGY = """
SELECT
    strategy,
    COUNT(*) AS total,
    SUM(CASE WHEN result = 'humans_win' THEN 1 ELSE 0 END) AS human_wins,
    ROUND(
        100.0 * SUM(CASE WHEN result = 'humans_win' THEN 1 ELSE 0 END) / COUNT(*), 2
    ) AS win_rate_pct
FROM simulations
WHERE result IS NOT NULL
GROUP BY strategy
ORDER BY win_rate_pct DESC;
"""

SELECT_SENSITIVITY_P_INFECT = """
SELECT
    ROUND(p_infect, 1) AS p_infect_bucket,
    COUNT(*) AS total,
    ROUND(
        100.0 * SUM(CASE WHEN result = 'humans_win' THEN 1 ELSE 0 END) / COUNT(*), 2
    ) AS win_rate_pct
FROM simulations
WHERE result IS NOT NULL
GROUP BY p_infect_bucket
ORDER BY p_infect_bucket;
"""
