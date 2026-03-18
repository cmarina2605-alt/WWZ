"""
test_db.py — Tests for the database layer.

Uses ":memory:" (SQLite in RAM) so tests are fast, isolated,
and do not pollute or depend on the simulations.db file on disk.

Test suites:
    TestSaveAndLoadSimulation   — save_simulation() returns ID > 0; data
                                  is recovered intact by seed; load_simulation
                                  returns None for non-existent seeds; simulation
                                  count is correct.
    TestSaveAndLoadEvents       — save_event() inserts without errors; get_events()
                                  returns events for the correct sim_id ordered by
                                  tick; events from different simulations don't mix.
    TestUpdateSimulationResult  — update_simulation_result() updates result,
                                  duration, humans_final and zombies_final correctly.
    TestStatsQueries            — analyze_strategies() returns win rates by strategy;
                                  sensitivity_analysis('p_infect') returns buckets;
                                  invalid parameters raise ValueError;
                                  get_best_strategy() returns the winning strategy
                                  or None if the DB is empty.
"""

import unittest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from db.stats import analyze_strategies, sensitivity_analysis, get_best_strategy


def _make_db() -> Database:
    """Creates an in-memory database for each test."""
    return Database(db_path=":memory:")


def _sim_data(**overrides) -> dict:
    """Generates a simulation data dict with default values."""
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
    """Tests for saving and loading simulations."""

    def test_save_returns_id(self) -> None:
        """save_simulation() returns a positive integer as ID."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        self.assertIsInstance(sim_id, int)
        self.assertGreater(sim_id, 0)

    def test_load_by_seed(self) -> None:
        """load_simulation(seed) returns the saved simulation."""
        db = _make_db()
        data = _sim_data(seed=99)
        db.save_simulation(data)
        loaded = db.load_simulation(99)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["seed"], 99)

    def test_load_nonexistent_seed(self) -> None:
        """load_simulation() returns None if the seed doesn't exist."""
        db = _make_db()
        result = db.load_simulation(9999)
        self.assertIsNone(result)

    def test_get_all_simulations_empty(self) -> None:
        """get_all_simulations() returns empty list if there is no data."""
        db = _make_db()
        sims = db.get_all_simulations()
        self.assertEqual(sims, [])

    def test_get_all_simulations_returns_list(self) -> None:
        """get_all_simulations() returns list with all simulations."""
        db = _make_db()
        db.save_simulation(_sim_data(seed=1))
        db.save_simulation(_sim_data(seed=2))
        db.save_simulation(_sim_data(seed=3))
        sims = db.get_all_simulations()
        self.assertEqual(len(sims), 3)

    def test_simulation_data_integrity(self) -> None:
        """Saved data is recovered intact."""
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
        """get_simulation_count() returns the correct number."""
        db = _make_db()
        self.assertEqual(db.get_simulation_count(), 0)
        db.save_simulation(_sim_data())
        db.save_simulation(_sim_data(seed=100))
        self.assertEqual(db.get_simulation_count(), 2)


class TestSaveAndLoadEvents(unittest.TestCase):
    """Tests for saving and loading events."""

    def test_save_event(self) -> None:
        """save_event() does not raise exceptions."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        db.save_event(sim_id, "infection", tick=10, description="Human infected")

    def test_get_events_by_sim(self) -> None:
        """get_events() returns events for the correct sim_id."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        db.save_event(sim_id, "infection", 5, "Infected A")
        db.save_event(sim_id, "death", 10, "Dead B")
        db.save_event(sim_id, "escape", 15, "Escaped C")

        events = db.get_events(sim_id)
        self.assertEqual(len(events), 3)

    def test_events_ordered_by_tick(self) -> None:
        """Events are returned ordered by tick."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        db.save_event(sim_id, "death", 30, "Late event")
        db.save_event(sim_id, "infection", 5, "Early event")
        db.save_event(sim_id, "escape", 15, "Mid event")

        events = db.get_events(sim_id)
        ticks = [e["tick"] for e in events]
        self.assertEqual(ticks, sorted(ticks))

    def test_events_isolated_by_sim(self) -> None:
        """Events from one simulation don't appear in another."""
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
        """get_events() returns empty list for simulation with no events."""
        db = _make_db()
        sim_id = db.save_simulation(_sim_data())
        events = db.get_events(sim_id)
        self.assertEqual(events, [])


class TestUpdateSimulationResult(unittest.TestCase):
    """Tests for result updates."""

    def test_update_result(self) -> None:
        """update_simulation_result() updates fields correctly."""
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
    """Tests for statistical analysis functions."""

    def _populate_db(self, db: Database) -> None:
        """Populates the DB with varied test data."""
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
        """analyze_strategies() returns a non-empty dict."""
        db = _make_db()
        self._populate_db(db)
        result = analyze_strategies(db)
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_analyze_strategies_has_flee(self) -> None:
        """analyze_strategies() includes the 'flee' strategy."""
        db = _make_db()
        self._populate_db(db)
        result = analyze_strategies(db)
        self.assertIn("flee", result)
        self.assertEqual(result["flee"]["total"], 3)

    def test_sensitivity_p_infect_returns_list(self) -> None:
        """sensitivity_analysis('p_infect') returns a list."""
        db = _make_db()
        self._populate_db(db)
        result = sensitivity_analysis("p_infect", db)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_sensitivity_invalid_param_raises(self) -> None:
        """sensitivity_analysis() raises ValueError with invalid parameter."""
        db = _make_db()
        with self.assertRaises(ValueError):
            sensitivity_analysis("invalid_param", db)

    def test_get_best_strategy(self) -> None:
        """get_best_strategy() returns the name of the winning strategy."""
        db = _make_db()
        self._populate_db(db)
        best = get_best_strategy(db)
        self.assertIsNotNone(best)
        self.assertIsInstance(best, str)

    def test_get_best_strategy_empty_db(self) -> None:
        """get_best_strategy() returns None if the DB is empty."""
        db = _make_db()
        best = get_best_strategy(db)
        self.assertIsNone(best)


if __name__ == "__main__":
    unittest.main()
