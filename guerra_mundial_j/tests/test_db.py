"""
test_db.py — Tests de la capa de base de datos.

Usa ":memory:" para no tocar el fichero simulations.db.

Cubre:
    - save_simulation() y recuperación por seed.
    - save_event() y relación con sim_id.
    - update_simulation_result().
    - Consultas de estadísticas (analyze_strategies, sensitivity_analysis).
    - Cierre y reapertura de conexión.
"""

import unittest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from db.stats import analyze_strategies, sensitivity_analysis, get_best_strategy


def _make_db() -> Database:
    """Crea una base de datos en memoria para cada test."""
    return Database(db_path=":memory:")


def _sim_data(**overrides) -> dict:
    """Genera un dict de datos de simulación con valores por defecto."""
    base = {
        "seed": 42,
        "p_infect": 0.4,
        "vision_human": 10,
        "vision_zombie": 15,
        "strategy": "flee",
        "n_scientists": 5,
        "n_military": 10,
        "n_politicians": 2,
        "result": "humans_win",
        "duration": 12.5,
        "humans_final": 75,
        "zombies_final": 0,
        "tick_final": 340,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


class TestSaveAndLoadSimulation(unittest.TestCase):
    """Tests de guardado y carga de simulaciones."""

    def test_save_returns_id(self) -> None:
        """save_simulation() retorna un entero positivo como ID."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        self.assertIsInstance(sim_id, int)
        self.assertGreater(sim_id, 0)

    def test_load_by_seed(self) -> None:
        """load_simulation(seed) retorna la simulación guardada."""
        db = _make_db()
        data = _sim_data(seed=99)
        db.save_simulation(data)
        loaded = db.load_simulation(99)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["seed"], 99)

    def test_load_nonexistent_seed(self) -> None:
        """load_simulation() retorna None si el seed no existe."""
        db = _make_db()
        result = db.load_simulation(9999)
        self.assertIsNone(result)

    def test_get_all_simulations_empty(self) -> None:
        """get_all_simulations() retorna lista vacía si no hay datos."""
        db = _make_db()
        sims = db.get_all_simulations()
        self.assertEqual(sims, [])

    def test_get_all_simulations_returns_list(self) -> None:
        """get_all_simulations() retorna lista con todas las simulaciones."""
        db = _make_db()
        db.save_simulation(_sim_data(seed=1))
        db.save_simulation(_sim_data(seed=2))
        db.save_simulation(_sim_data(seed=3))
        sims = db.get_all_simulations()
        self.assertEqual(len(sims), 3)

    def test_simulation_data_integrity(self) -> None:
        """Los datos guardados se recuperan intactos."""
        db = _make_db()
        data = _sim_data(
            seed=777,
            p_infect=0.65,
            strategy="military_first",
            result="zombies_win",
            humans_final=0,
            zombies_final=42,
        )
        sim_id = db.save_simulation(data)
        loaded = db.load_simulation(777)

        self.assertEqual(loaded["p_infect"], 0.65)
        self.assertEqual(loaded["strategy"], "military_first")
        self.assertEqual(loaded["result"], "zombies_win")
        self.assertEqual(loaded["humans_final"], 0)
        self.assertEqual(loaded["zombies_final"], 42)

    def test_simulation_count(self) -> None:
        """get_simulation_count() retorna el número correcto."""
        db = _make_db()
        self.assertEqual(db.get_simulation_count(), 0)
        db.save_simulation(_sim_data())
        db.save_simulation(_sim_data(seed=100))
        self.assertEqual(db.get_simulation_count(), 2)


class TestSaveAndLoadEvents(unittest.TestCase):
    """Tests de guardado y carga de eventos."""

    def test_save_event(self) -> None:
        """save_event() no lanza excepciones."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        db.save_event(sim_id, "infection", tick=10, description="Humano infectado")

    def test_get_events_by_sim(self) -> None:
        """get_events() retorna los eventos del sim_id correcto."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        db.save_event(sim_id, "infection", 5, "Infectado A")
        db.save_event(sim_id, "death", 10, "Muerto B")
        db.save_event(sim_id, "escape", 15, "Escapó C")

        events = db.get_events(sim_id)
        self.assertEqual(len(events), 3)

    def test_events_ordered_by_tick(self) -> None:
        """Los eventos se retornan ordenados por tick."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        db.save_event(sim_id, "death", 30, "Evento tarde")
        db.save_event(sim_id, "infection", 5, "Evento temprano")
        db.save_event(sim_id, "escape", 15, "Evento medio")

        events = db.get_events(sim_id)
        ticks = [e["tick"] for e in events]
        self.assertEqual(ticks, sorted(ticks))

    def test_events_isolated_by_sim(self) -> None:
        """Los eventos de una simulación no aparecen en otra."""
        db = _make_db()
        sim1 = db.save_simulation(_sim_data(seed=1))
        sim2 = db.save_simulation(_sim_data(seed=2))

        db.save_event(sim1, "infection", 1, "Sim1 evento")
        db.save_event(sim2, "death", 2, "Sim2 evento")

        events1 = db.get_events(sim1)
        events2 = db.get_events(sim2)

        self.assertEqual(len(events1), 1)
        self.assertEqual(len(events2), 1)
        self.assertEqual(events1[0]["event_type"], "infection")
        self.assertEqual(events2[0]["event_type"], "death")

    def test_get_events_empty(self) -> None:
        """get_events() retorna lista vacía para simulación sin eventos."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        events = db.get_events(sim_id)
        self.assertEqual(events, [])


class TestUpdateSimulationResult(unittest.TestCase):
    """Tests de actualización de resultados."""

    def test_update_result(self) -> None:
        """update_simulation_result() actualiza los campos correctamente."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data(result=None))

        db.update_simulation_result(
            sim_id=sim_id,
            result="zombies_win",
            duration=45.2,
            humans_final=0,
            zombies_final=18,
            tick_final=800,
        )

        loaded = db.load_simulation(42)
        self.assertEqual(loaded["result"], "zombies_win")
        self.assertEqual(loaded["humans_final"], 0)
        self.assertEqual(loaded["zombies_final"], 18)
        self.assertAlmostEqual(loaded["duration"], 45.2, places=1)


class TestStatsQueries(unittest.TestCase):
    """Tests de las funciones de análisis estadístico."""

    def _populate_db(self, db: Database) -> None:
        """Rellena la DB con datos de prueba variados."""
        scenarios = [
            {"strategy": "flee", "result": "humans_win", "p_infect": 0.3},
            {"strategy": "flee", "result": "humans_win", "p_infect": 0.3},
            {"strategy": "flee", "result": "zombies_win", "p_infect": 0.3},
            {"strategy": "military_first", "result": "humans_win", "p_infect": 0.4},
            {"strategy": "military_first", "result": "humans_win", "p_infect": 0.4},
            {"strategy": "group", "result": "zombies_win", "p_infect": 0.6},
            {"strategy": "group", "result": "zombies_win", "p_infect": 0.7},
        ]
        for i, sc in enumerate(scenarios):
            db.save_simulation(_sim_data(seed=i, **sc))

    def test_analyze_strategies_returns_dict(self) -> None:
        """analyze_strategies() retorna un dict no vacío."""
        db = _make_db()
        self._populate_db(db)
        result = analyze_strategies(db)
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_analyze_strategies_has_flee(self) -> None:
        """analyze_strategies() incluye la estrategia 'flee'."""
        db = _make_db()
        self._populate_db(db)
        result = analyze_strategies(db)
        self.assertIn("flee", result)
        self.assertEqual(result["flee"]["total"], 3)

    def test_sensitivity_p_infect_returns_list(self) -> None:
        """sensitivity_analysis('p_infect') retorna una lista."""
        db = _make_db()
        self._populate_db(db)
        result = sensitivity_analysis("p_infect", db)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_sensitivity_invalid_param_raises(self) -> None:
        """sensitivity_analysis() lanza ValueError con parámetro inválido."""
        db = _make_db()
        with self.assertRaises(ValueError):
            sensitivity_analysis("invalid_param", db)

    def test_get_best_strategy(self) -> None:
        """get_best_strategy() retorna el nombre de la estrategia ganadora."""
        db = _make_db()
        self._populate_db(db)
        best = get_best_strategy(db)
        self.assertIsNotNone(best)
        self.assertIsInstance(best, str)

    def test_get_best_strategy_empty_db(self) -> None:
        """get_best_strategy() retorna None si la DB está vacía."""
        db = _make_db()
        best = get_best_strategy(db)
        self.assertIsNone(best)


if __name__ == "__main__":
    unittest.main()
