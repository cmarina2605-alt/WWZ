"""
db — Simulation data persistence package.

Saves the results of each simulation in SQLite (simulations.db)
for later analysis: which strategy wins most, sensitivity to
parameters like p_infect, impact of military percentage, etc.

Modules:
    models.py   — SQL schema (CREATE TABLE), parameterized queries
                  and statistical analysis queries.
    database.py — Database class: thread-safe wrapper over sqlite3.
                  Methods: save_simulation, save_event, get_events,
                  update_simulation_result, load_simulation, etc.
    stats.py    — Analysis functions: win rate by strategy,
                  sensitivity to p_infect/vision, console summary.

SQLite tables:
    simulations — One row per simulation: seed, parameters, result,
                  duration, final counts, final tick, timestamp.
    events      — One row per key event (infection, death, antidote...):
                  sim_id (FK), event_type, tick, description.
"""

from db.database import Database
from db.models import SCHEMA_SQL

__all__ = [
    "Database",
    "SCHEMA_SQL",
]
