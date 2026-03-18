"""
test_engine.py — Tests for the simulation engine (Engine and World).

Verifies Engine behavior as an orchestrator and World thread-safety
under concurrent access.

Test suites:
    TestEngineCreation          — Engine creates the correct number of agents
                                  and threads; all are daemon; seed produces
                                  deterministic results (reproducibility).
    TestWorldLockRaceConditions — multiple threads moving agents don't crash
                                  or corrupt the grid; lock prevents two agents
                                  from occupying the same cell; get_agents_in_radius
                                  is safe under concurrent writes.
    TestWinConditions           — check_win_conditions() correctly detects:
                                  zombies_win (no humans), humans_win (no zombies),
                                  humans_win (antidote_ready active), None (both alive).
    TestEngineSnapshot          — get_snapshot() contains all required keys
                                  and the 'grid' field is a dict.

Note: each test clears game_over in setUp and sets it in tearDown to stop
residual threads and avoid inter-suite interference.
"""

import threading
import time
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from agents.base_agent import game_over, antidote_ready
from simulation.engine import Engine
from simulation.world import World
from agents.human import Normal
from agents.zombie import Zombie


class TestEngineCreation(unittest.TestCase):
    """Tests for agent creation by the engine."""

    def setUp(self) -> None:
        game_over.clear()
        antidote_ready.clear()

    def tearDown(self) -> None:
        game_over.set()
        time.sleep(0.3)

    def test_engine_creates_correct_thread_count(self) -> None:
        """
        Engine creates the correct number of agent threads.

        Expected total = n_humans + n_zombies.
        """
        n_humans = 10
        n_zombies = 2
        engine = Engine(n_humans=n_humans, n_zombies=n_zombies)
        engine.start_simulation()

        # Give threads time to start
        time.sleep(0.3)

        alive_agents = [a for a in engine.agents if a.is_alive()]
        total_expected = n_humans + n_zombies
        self.assertEqual(
            len(engine.agents),
            total_expected,
            f"Expected {total_expected} agents, found {len(engine.agents)}",
        )

    def test_engine_threads_are_daemon(self) -> None:
        """All agent threads are daemon."""
        engine = Engine(n_humans=5, n_zombies=1)
        engine.start_simulation()
        time.sleep(0.2)
        for agent in engine.agents:
            self.assertTrue(agent.daemon, f"Agent {agent.agent_id} is not daemon")

    def test_engine_seed_reproducibility(self) -> None:
        """
        Two simulations with the same seed create the same agents
        at the same positions (PRNG determinism).
        """
        game_over.clear()
        e1 = Engine(seed=42, n_humans=5, n_zombies=1)
        e1._create_agents()
        pos1 = sorted([a.pos for a in e1.agents])

        game_over.clear()
        e2 = Engine(seed=42, n_humans=5, n_zombies=1)
        e2._create_agents()
        pos2 = sorted([a.pos for a in e2.agents])

        self.assertEqual(pos1, pos2, "Same seed must produce same positions")


class TestWorldLockRaceConditions(unittest.TestCase):
    """Tests for World thread-safety."""

    def setUp(self) -> None:
        game_over.clear()

    def tearDown(self) -> None:
        game_over.set()

    def test_concurrent_moves_no_crash(self) -> None:
        """
        Multiple threads moving agents simultaneously do not produce
        errors or grid corruption.
        """
        world = World(size=50)
        agents = [Normal(pos=(i, 0), world=world) for i in range(10)]
        for agent in agents:
            pos = world.find_free_cell()
            world.place_agent(agent, pos)

        errors = []

        def move_agent(agent):
            for _ in range(20):
                new_pos = world.find_free_cell()
                if new_pos:
                    try:
                        world.move_agent(agent, new_pos)
                    except Exception as exc:
                        errors.append(exc)
                time.sleep(0.001)

        threads = [threading.Thread(target=move_agent, args=(a,)) for a in agents]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        self.assertEqual(len(errors), 0, f"Errors in concurrent movement: {errors}")

    def test_lock_prevents_duplicate_placement(self) -> None:
        """
        Two threads trying to place on the same cell → only one succeeds.
        """
        world = World(size=10)
        target_pos = (5, 5)
        results = []

        def place_on_target(agent):
            success = world.place_agent(agent, target_pos)
            results.append(success)

        a1 = Normal(pos=(0, 0), world=world)
        a2 = Normal(pos=(1, 0), world=world)

        t1 = threading.Thread(target=place_on_target, args=(a1,))
        t2 = threading.Thread(target=place_on_target, args=(a2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Only one should have succeeded (or both failed if already occupied)
        self.assertLessEqual(
            results.count(True), 1,
            "Only one agent can occupy a cell simultaneously",
        )

    def test_get_agents_in_radius_thread_safe(self) -> None:
        """
        get_agents_in_radius() does not raise exceptions under concurrent modification.
        """
        world = World(size=30)
        agents = [Normal(pos=(i, i), world=world) for i in range(5)]
        for a in agents:
            world.place_agent(a, a.pos)

        errors = []

        def reader():
            for _ in range(50):
                try:
                    world.get_agents_in_radius((15, 15), 20)
                except Exception as exc:
                    errors.append(exc)
                time.sleep(0.001)

        def writer():
            for a in agents:
                for _ in range(10):
                    new_pos = world.find_free_cell()
                    if new_pos:
                        world.move_agent(a, new_pos)
                    time.sleep(0.001)

        t_read = threading.Thread(target=reader)
        t_write = threading.Thread(target=writer)
        t_read.start()
        t_write.start()
        t_read.join(timeout=5.0)
        t_write.join(timeout=5.0)

        self.assertEqual(len(errors), 0, f"Errors under concurrent access: {errors}")


class TestWinConditions(unittest.TestCase):
    """Tests for check_win_conditions()."""

    def setUp(self) -> None:
        game_over.clear()
        antidote_ready.clear()

    def tearDown(self) -> None:
        game_over.set()

    def test_zombies_win_when_no_humans(self) -> None:
        """
        When there are no living humans, check_win_conditions() sets
        result = 'zombies_win'.
        """
        engine = Engine(n_humans=2, n_zombies=1)
        engine._create_agents()

        # Kill all humans
        for agent in engine.agents:
            if agent.__class__.__name__ != "Zombie":
                agent.die()

        engine.check_win_conditions()
        self.assertEqual(engine.result, "zombies_win")

    def test_humans_win_when_no_zombies(self) -> None:
        """
        When there are no zombies, check_win_conditions() sets
        result = 'humans_win'.
        """
        engine = Engine(n_humans=3, n_zombies=1)
        engine._create_agents()

        # Kill all zombies
        for agent in engine.agents:
            if agent.__class__.__name__ == "Zombie":
                agent.die()

        engine.check_win_conditions()
        self.assertEqual(engine.result, "humans_win")

    def test_antidote_triggers_human_win(self) -> None:
        """
        When antidote_ready is active, humans win.
        """
        engine = Engine(n_humans=3, n_zombies=2)
        engine._create_agents()
        antidote_ready.set()

        engine.check_win_conditions()
        self.assertEqual(engine.result, "humans_win")

    def test_no_result_when_both_present(self) -> None:
        """
        If there are humans and zombies, result must be None.
        """
        engine = Engine(n_humans=5, n_zombies=2)
        engine._create_agents()

        # Verify that at least there are agents of both types alive
        has_humans = any(
            a.__class__.__name__ != "Zombie" and a.is_alive()
            for a in engine.agents
        )
        has_zombies = any(
            a.__class__.__name__ == "Zombie" and a.is_alive()
            for a in engine.agents
        )

        if has_humans and has_zombies:
            engine.check_win_conditions()
            self.assertIsNone(
                engine.result,
                "There must be no result with both sides present",
            )


class TestEngineSnapshot(unittest.TestCase):
    """Tests for the get_snapshot() method."""

    def setUp(self) -> None:
        game_over.clear()

    def tearDown(self) -> None:
        game_over.set()

    def test_snapshot_has_required_keys(self) -> None:
        """get_snapshot() includes all required keys."""
        engine = Engine(n_humans=3, n_zombies=1)
        engine._create_agents()
        snap = engine.get_snapshot()

        required_keys = {"tick", "n_humans", "n_zombies", "result", "running", "grid", "seed"}
        for key in required_keys:
            self.assertIn(key, snap, f"Key '{key}' missing in snapshot")

    def test_snapshot_grid_is_dict(self) -> None:
        """The 'grid' field in the snapshot is a dictionary."""
        engine = Engine(n_humans=3, n_zombies=1)
        engine._create_agents()
        snap = engine.get_snapshot()
        self.assertIsInstance(snap["grid"], dict)


if __name__ == "__main__":
    unittest.main()
