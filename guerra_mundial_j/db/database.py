"""
database.py — Capa de acceso a datos SQLite para la simulación.

La clase Database es un wrapper thread-safe sobre sqlite3 que encapsula
todas las operaciones CRUD sobre simulations.db. Todos los métodos
adquieren un threading.Lock interno antes de acceder a la conexión,
por lo que puede llamarse desde múltiples threads sin riesgo de corrupción.

Métodos de escritura:
    save_simulation(data)           — inserta una simulación, retorna su ID.
    save_event(sim_id, type, tick, desc) — añade un evento a una simulación.
    update_simulation_result(...)   — actualiza resultado, duración y conteos
                                      finales cuando la simulación termina.

Métodos de lectura:
    get_all_simulations()           — todas las simulaciones, más reciente primero.
    load_simulation(seed)           — simulación más reciente con ese seed.
    get_events(sim_id)              — eventos de una simulación, ordenados por tick.
    get_simulation_count()          — número total de simulaciones en la DB.

Uso típico:
    db = Database()           # abre/crea simulations.db
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
    Clase de acceso a la base de datos SQLite de la simulación.

    Gestiona la conexión y provee métodos CRUD de alto nivel para
    simulations y events. Thread-safe gracias a un Lock interno.

    Attributes:
        db_path (str): Ruta al fichero SQLite (":memory:" para tests).
        _conn (sqlite3.Connection): Conexión activa.
        _lock (threading.Lock): Protege accesos concurrentes.
    """

    def __init__(self, db_path: str = config.DB_PATH) -> None:
        """
        Inicializa la base de datos y crea las tablas si no existen.

        Args:
            db_path: Ruta al fichero .db. Usa ":memory:" para tests.
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
    # Inicialización
    # ------------------------------------------------------------------

    def init_db(self) -> None:
        """
        Crea las tablas e índices si no existen todavía.

        Ejecuta el SCHEMA_SQL completo de models.py.
        """
        with self._lock:
            cursor = self._conn.cursor()
            # Ejecutar sentencias individuales (executescript ignora params)
            for statement in SCHEMA_SQL.split(";"):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def save_simulation(self, data: Dict[str, Any]) -> int:
        """
        Guarda los datos de una simulación y retorna su ID.

        Args:
            data: Diccionario con los campos de la tabla simulations.
                  Claves esperadas: seed, p_infect, vision_human,
                  vision_zombie, strategy, n_scientists, n_military,
                  n_politicians, result, duration, humans_final,
                  zombies_final, tick_final.

        Returns:
            int: ID asignado a la simulación guardada.
        """
        # Añadir timestamp si no viene en data
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Valores por defecto para campos opcionales
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
        Guarda un evento asociado a una simulación.

        Args:
            sim_id: ID de la simulación a la que pertenece el evento.
            event_type: Tipo de evento (e.g. "infection", "death").
            tick: Tick en que ocurrió el evento.
            description: Descripción legible del evento.
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
        Actualiza el resultado de una simulación ya guardada.

        Args:
            sim_id: ID de la simulación.
            result: "humans_win" | "zombies_win".
            duration: Duración en segundos.
            humans_final: Humanos vivos al final.
            zombies_final: Zombis al final.
            tick_final: Tick en que terminó.
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
    # Lectura
    # ------------------------------------------------------------------

    def get_all_simulations(self) -> List[Dict[str, Any]]:
        """
        Retorna todas las simulaciones guardadas, ordenadas por fecha.

        Returns:
            Lista de dicts con los datos de cada simulación.
        """
        with self._lock:
            cursor = self._conn.execute(SELECT_ALL_SIMULATIONS)
            return [dict(row) for row in cursor.fetchall()]

    def load_simulation(self, seed: int) -> Optional[Dict[str, Any]]:
        """
        Carga la simulación más reciente con el seed dado.

        Args:
            seed: Semilla aleatoria a buscar.

        Returns:
            Dict con los datos de la simulación, o None si no existe.
        """
        with self._lock:
            cursor = self._conn.execute(SELECT_SIMULATION_BY_SEED, (seed,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_events(self, sim_id: int) -> List[Dict[str, Any]]:
        """
        Retorna todos los eventos de una simulación.

        Args:
            sim_id: ID de la simulación.

        Returns:
            Lista de dicts con los eventos, ordenados por tick.
        """
        with self._lock:
            cursor = self._conn.execute(SELECT_EVENTS_BY_SIM, (sim_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_simulation_count(self) -> int:
        """
        Retorna el número total de simulaciones guardadas.

        Returns:
            int: Número de filas en la tabla simulations.
        """
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM simulations")
            return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Limpieza
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Cierra la conexión a la base de datos."""
        with self._lock:
            self._conn.close()

    def __repr__(self) -> str:
        return f"Database(path={self.db_path!r})"
