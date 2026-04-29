"""
database.py — Singleton SQLite data access layer with batched write queue.

Design Pattern: SINGLETON
    Ensures only one Database instance exists across the entire simulation.
    Since sqlite3.Connection can only be safely used from the thread that
    created it, the Singleton wraps a queue.Queue and a dedicated writer
    thread. Agent threads call db.log_event() which enqueues a dict and
    returns immediately (non-blocking). The writer thread batches inserts
    into transactions, avoiding one-commit-per-event overhead.

Benefits:
    - Agent threads never block on disk I/O.
    - Batched writes: multiple events per transaction improve throughput.
    - Thread-safe by construction (queue + dedicated writer).
    - Single instance prevents accidental multiple connections.

Usage:
    db = Database()               # always returns the same instance
    db.log_event(sim_id, "infection", tick=42, description="...")
    db.save_simulation({...})     # synchronous (for batch mode)
    db.close()                    # stops writer thread and flushes

References:
    https://refactoring.guru/design-patterns/singleton
"""

import sqlite3
import threading
import queue
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


class _DatabaseMeta(type):
    """
    Thread-safe Singleton metaclass for Database (keyed by db_path).

    Guarantees that Database() always returns the same instance
    for a given db_path, even if called simultaneously from multiple
    threads. Different paths (e.g. ":memory:" for tests) get their own
    instances.
    """
    _instances: dict = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        # Use db_path as the key so tests with ":memory:" get separate instances.
        # ":memory:" always creates a new instance (each one is independent).
        db_path = args[0] if args else kwargs.get("db_path", config.DB_PATH)
        if db_path == ":memory:":
            return super().__call__(*args, **kwargs)
        with cls._lock:
            if db_path not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[db_path] = instance
            return cls._instances[db_path]


class Database(metaclass=_DatabaseMeta):
    """
    Singleton SQLite database with a dedicated writer thread.

    The writer thread consumes from an internal queue and batches
    writes into transactions. Read operations use a separate connection
    with a lock for thread safety.

    Attributes:
        db_path (str): Path to the SQLite file.
        _write_queue (queue.Queue): Queue for non-blocking event inserts.
        _writer_thread (threading.Thread): Dedicated writer thread.
        _conn (sqlite3.Connection): Connection for reads (+ sync writes).
        _lock (threading.Lock): Protects _conn for reads.
    """

    BATCH_SIZE = 50          # Max events per transaction
    FLUSH_INTERVAL = 0.5     # Seconds between batch flushes

    def __init__(self, db_path: str = config.DB_PATH) -> None:
        self.db_path: str = db_path
        self._lock: threading.Lock = threading.Lock()
        self._write_queue: queue.Queue = queue.Queue()
        self._running: bool = True

        # Main connection (reads + synchronous writes like save_simulation)
        self._conn: sqlite3.Connection = sqlite3.connect(
            db_path,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self.init_db()

        # Start dedicated writer thread for async event logging
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            daemon=True,
            name="DB-Writer",
        )
        self._writer_thread.start()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def init_db(self) -> None:
        """Creates tables and indexes if they don't exist. Enables WAL mode."""
        with self._lock:
            # WAL mode allows concurrent reads while writing,
            # which is ideal for our multi-threaded simulation
            self._conn.execute("PRAGMA journal_mode=WAL")
            cursor = self._conn.cursor()
            for statement in SCHEMA_SQL.split(";"):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Async event writer (batched transactions)
    # ------------------------------------------------------------------

    def _writer_loop(self) -> None:
        """
        Dedicated writer thread that consumes events from the queue
        and batches them into SQLite transactions.

        This avoids one INSERT + COMMIT per event, which is the main
        bottleneck for SQLite under multi-threaded workloads.
        """
        # Separate connection for the writer thread (sqlite3 requirement)
        writer_conn = sqlite3.connect(self.db_path)

        while self._running or not self._write_queue.empty():
            batch: List[tuple] = []
            try:
                # Wait for the first item (blocking)
                item = self._write_queue.get(timeout=self.FLUSH_INTERVAL)
                batch.append(item)
                self._write_queue.task_done()
            except queue.Empty:
                continue

            # Drain up to BATCH_SIZE more items without blocking
            while len(batch) < self.BATCH_SIZE:
                try:
                    item = self._write_queue.get_nowait()
                    batch.append(item)
                    self._write_queue.task_done()
                except queue.Empty:
                    break

            # Execute batch in a single transaction
            if batch:
                try:
                    cursor = writer_conn.cursor()
                    for sim_id, event_type, tick, description in batch:
                        cursor.execute(
                            INSERT_EVENT,
                            (sim_id, event_type, tick, description),
                        )
                    writer_conn.commit()
                except Exception as exc:
                    print(f"[DB-Writer] Error writing batch: {exc}")

        writer_conn.close()

    def log_event(
        self,
        sim_id: int,
        event_type: str,
        tick: int,
        description: str,
    ) -> None:
        """
        Non-blocking event log: enqueues the event for batched writing.

        Agent threads call this instead of save_event() so they never
        block on disk I/O.

        Args:
            sim_id: Simulation ID.
            event_type: Event type string.
            tick: Simulation tick.
            description: Human-readable description.
        """
        self._write_queue.put((sim_id, event_type, tick, description))

    # ------------------------------------------------------------------
    # Synchronous write methods (for batch mode / end-of-sim)
    # ------------------------------------------------------------------

    def save_simulation(self, data: Dict[str, Any]) -> int:
        """
        Saves simulation data (synchronous). Returns the assigned ID.

        Args:
            data: Dict with simulation table fields.

        Returns:
            int: ID of the saved simulation.
        """
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

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
        """Synchronous event save (backward compatibility)."""
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
        """Updates the result of an already saved simulation."""
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

    def execute_query(
        self, sql: str, params: tuple = ()
    ) -> List[Dict[str, Any]]:
        """
        Executes a read-only SQL query and returns a list of row dicts.

        This is the public API for running arbitrary SELECT queries
        against the database. It acquires the internal lock, executes
        the query, and returns the results as a list of dictionaries.

        Args:
            sql: SQL SELECT statement to execute.
            params: Optional tuple of query parameters.

        Returns:
            List of dicts, one per row.
        """
        with self._lock:
            cursor = self._conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_all_simulations(self) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute(SELECT_ALL_SIMULATIONS)
            return [dict(row) for row in cursor.fetchall()]

    def load_simulation(self, seed: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute(SELECT_SIMULATION_BY_SEED, (seed,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_events(self, sim_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute(SELECT_EVENTS_BY_SIM, (sim_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_simulation_count(self) -> int:
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM simulations")
            return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Stops the writer thread, flushes remaining events, and closes."""
        self._running = False
        if self._writer_thread.is_alive():
            self._writer_thread.join(timeout=3.0)
        with self._lock:
            self._conn.close()

    def __repr__(self) -> str:
        return f"Database(path={self.db_path!r}, queue_size={self._write_queue.qsize()})"
