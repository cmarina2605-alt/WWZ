"""
database.py — SQLite data access layer for the simulation.

The Database class is a thread-safe wrapper over sqlite3 that encapsulates
all CRUD operations on simulations.db. All methods acquire an internal
threading.Lock before accessing the connection, so it can be called from
multiple threads without risk of corruption.

Write methods:
    save_simulation(data)           — inserts a simulation, returns its ID.
    save_event(sim_id, type, tick, desc) — adds an event to a simulation.
    update_simulation_result(...)   — updates result, duration and final
                                      counts when the simulation ends.

Read methods:
    get_all_simulations()           — all simulations, most recent first.
    load_simulation(seed)           — most recent simulation with that seed.
    get_events(sim_id)              — events of a simulation, ordered by tick.
    get_simulation_count()          — total number of simulations in the DB.

Typical usage:
    db = Database()           # opens/creates simulations.db
    sim_id = db.save_simulation({...})
    db.save_event(sim_id, "antidote", tick=420, description="...")
    db.close()
"""

import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import config
from db.models import (
    SCHEMA_SQL,
    INSERT_SIMULATION,
    INSERT_EVENT,
    SELECT_ALL_SIMULATIONS,
    SELECT_SIMULATION_BY_SEED,
    SELECT_EVENTS_BY_SIM,
)


class Database:
    """
    SQLite database access class for the simulation.

    Manages the connection and provides high-level CRUD methods for
    simulations and events. Thread-safe thanks to an internal Lock.

    Attributes:
        db_path (str): Path to the SQLite file (":memory:" for tests).
        _conn (sqlite3.Connection): Active connection.
        _lock (threading.Lock): Protects concurrent access.
    """

    def __init__(self, db_path: str = config.DB_PATH) -> None:
        """
        Initializes the database and creates tables if they don't exist.

        Args:
            db_path: Path to the .db file. Use ":memory:" for tests.
        """
        self.db_path: str = db_path
        self._lock: threading.Lock = threading.Lock()
        self._conn: sqlite3.Connection = sqlite3.connect(
            db_path,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self.init_db()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def init_db(self) -> None:
        """
        Creates tables and indexes if they don't exist yet.

        Runs the full SCHEMA_SQL from models.py.
        """
        with self._lock:
            cursor = self._conn.cursor()
            # Execute individual statements (executescript ignores params)
            for statement in SCHEMA_SQL.split(";"):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def save_simulation(self, data: Dict[str, Any]) -> int:
        """
        Saves simulation data and returns its ID.

        Args:
            data: Dict with simulations table fields.
                  Expected keys: seed, p_infect, vision_human,
                  vision_zombie, strategy, n_scientists, n_military,
                  n_politicians, result, duration, humans_final,
                  zombies_final, tick_final.

        Returns:
            int: ID assigned to the saved simulation.
        """
        # Add timestamp if not in data
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Default values for optional fields
        defaults: Dict[str, Any] = {
            "vision_human": config.VISION_HUMAN,
            "vision_zombie": config.VISION_ZOMBIE,
            "n_scientists": config.NUM_SCIENTISTS,
            "n_military": config.NUM_MILITARY,
            "n_politicians": config.NUM_POLITICIANS,
            "result": None,
            "duration": None,
            "humans_final": None,
            "zombies_final": None,
            "tick_final": None,
        }
        for key, val in defaults.items():
            data.setdefault(key, val)

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(INSERT_SIMULATION, data)
            self._conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def save_event(
        self,
        sim_id: int,
        event_type: str,
        tick: int,
        description: str,
    ) -> None:
        """
        Saves an event associated with a simulation.

        Args:
            sim_id: ID of the simulation the event belongs to.
            event_type: Event type (e.g. "infection", "death").
            tick: Tick when the event occurred.
            description: Human-readable description of the event.
        """
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(INSERT_EVENT, (sim_id, event_type, tick, description))
            self._conn.commit()

    def update_simulation_result(
        self,
        sim_id: int,
        result: str,
        duration: float,
        humans_final: int,
        zombies_final: int,
        tick_final: int,
    ) -> None:
        """
        Updates the result of an already saved simulation.

        Args:
            sim_id: Simulation ID.
            result: "humans_win" | "zombies_win".
            duration: Duration in seconds.
            humans_final: Living humans at the end.
            zombies_final: Zombies at the end.
            tick_final: Tick when it ended.
        """
        sql = """
            UPDATE simulations
            SET result = ?, duration = ?, humans_final = ?,
                zombies_final = ?, tick_final = ?
            WHERE id = ?
        """
        with self._lock:
            self._conn.execute(
                sql,
                (result, duration, humans_final, zombies_final, tick_final, sim_id),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_all_simulations(self) -> List[Dict[str, Any]]:
        """
        Returns all saved simulations, ordered by date.

        Returns:
            List of dicts with each simulation's data.
        """
        with self._lock:
            cursor = self._conn.execute(SELECT_ALL_SIMULATIONS)
            return [dict(row) for row in cursor.fetchall()]

    def load_simulation(self, seed: int) -> Optional[Dict[str, Any]]:
        """
        Loads the most recent simulation with the given seed.

        Args:
            seed: Random seed to search for.

        Returns:
            Dict with simulation data, or None if not found.
        """
        with self._lock:
            cursor = self._conn.execute(SELECT_SIMULATION_BY_SEED, (seed,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_events(self, sim_id: int) -> List[Dict[str, Any]]:
        """
        Returns all events of a simulation.

        Args:
            sim_id: Simulation ID.

        Returns:
            List of event dicts, ordered by tick.
        """
        with self._lock:
            cursor = self._conn.execute(SELECT_EVENTS_BY_SIM, (sim_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_simulation_count(self) -> int:
        """
        Returns the total number of saved simulations.

        Returns:
            int: Number of rows in the simulations table.
        """
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM simulations")
            return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Closes the database connection."""
        with self._lock:
            self._conn.close()

    def __repr__(self) -> str:
        return f"Database(path={self.db_path!r})"
