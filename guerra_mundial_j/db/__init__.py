"""
db — Paquete de persistencia de datos de la simulación.

Guarda los resultados de cada simulación en SQLite (simulations.db)
para análisis posterior: qué estrategia gana más, sensibilidad a
parámetros como p_infect, impacto del porcentaje de militares, etc.

Módulos:
    models.py   — Esquema SQL (CREATE TABLE), queries parametrizadas
                  y queries de análisis estadístico.
    database.py — Clase Database: wrapper thread-safe sobre sqlite3.
                  Métodos: save_simulation, save_event, get_events,
                  update_simulation_result, load_simulation, etc.
    stats.py    — Funciones de análisis: tasa de victoria por estrategia,
                  sensibilidad a p_infect/visión, resumen en consola.

Tablas SQLite:
    simulations — Una fila por simulación: seed, parámetros, resultado,
                  duración, conteos finales, tick final, timestamp.
    events      — Una fila por evento clave (infección, muerte, antídoto...):
                  sim_id (FK), event_type, tick, descripción.
"""

from db.database import Database
from db.models import SCHEMA_SQL

__all__ = [
    "Database",
    "SCHEMA_SQL",
]
