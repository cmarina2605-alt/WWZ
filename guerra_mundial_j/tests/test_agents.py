"""
test_agents.py — Unit tests for agents (Human and Zombie).

Verifies that agent classes behave correctly in isolation,
without needing to run a full simulation.

Test suites:
    TestAgentInstantiation  — agents are created with correct attributes,
                              unique IDs and force clamped to [0, 100].
    TestGameOverRespect     — agent thread stops when game_over is set,
                              and doesn't start if already active.
    TestMilitaryAttributes  — strength bonus, ammo consumption and role.
    TestScientistAttributes — intelligence, initial antidote_progress and role.
    TestPoliticianAttributes — influence, high empathy by default and role.
    TestStateTransitions    — valid states are assigned; invalid states
                              raise ValueError; infect() and die() work.

Tests use 20×20 Worlds for speed and global signals (game_over, antidote_ready,
national_alert) are cleared in setUp and set in tearDown to avoid orphan threads.
"""

import threading
import time
import unittest

# Ensure project imports work
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from agents.base_agent import game_over, antidote_ready, national_alert, _generate_id
from agents.human import Human, Normal, Scientist, Military, Politician
from agents.zombie import Zombie
from simulation.world import World


def _make_world() -> World:
    """Creates a small World for tests."""
    return World(size=20)


def _place(agent, world: World) -> None:
    """Places an agent in the world (finds a free cell)."""
    pos = world.find_free_cell()
    assert pos is not None
    world.place_agent(agent, pos)


class TestAgentInstantiation(unittest.TestCase):
    """Basic instantiation tests."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()  # Stop any live threads

    def test_human_normal_instantiation(self) -> None:
        """Normal is instantiated with correct attributes."""
        h = Normal(pos=(0, 0), world=self.world, force=60, age=25)
        self.assertEqual(h.role, "normal")
        self.assertEqual(h.force, 60)
        self.assertEqual(h.age, 25)
        self.assertEqual(h.state, "calm")
        self.assertIsNotNone(h.agent_id)
        self.assertIsInstance(h, Human)

    def test_zombie_instantiation(self) -> None:
        """Zombie is instantiated with correct attributes."""
        z = Zombie(pos=(5, 5), world=self.world, force=70)
        self.assertEqual(z.state, "calm")
        self.assertIsNone(z.target_id)
        self.assertEqual(z.infection_count, 0)
        self.assertIsInstance(z, Zombie)

    def test_unique_ids(self) -> None:
        """Each agent has a unique ID."""
        w = _make_world()
        agents = [Normal(pos=(i, 0), world=w) for i in range(5)]
        ids = [a.agent_id for a in agents]
        self.assertEqual(len(ids), len(set(ids)), "IDs must be unique")

    def test_force_clamped(self) -> None:
        """Force is clamped to [0, 100]."""
        h1 = Normal(pos=(0, 0), world=self.world, force=200)
        h2 = Normal(pos=(1, 0), world=self.world, force=-50)
        self.assertEqual(h1.force, 100)
        self.assertEqual(h2.force, 0)


class TestGameOverRespect(unittest.TestCase):
    """Tests for game_over event respect in the run() loop."""

    def setUp(self) -> None:
        game_over.clear()
        antidote_ready.clear()
        national_alert.clear()

    def test_agent_stops_when_game_over(self) -> None:
        """
        Agent must stop when game_over is set.

        The thread must finish within 2 seconds after game_over is activated.
        """
        world = _make_world()
        z = Zombie(pos=(0, 0), world=world)
        world.place_agent(z, (0, 0))

        z.start()
        self.assertTrue(z.is_alive())

        game_over.set()
        z.join(timeout=2.0)

        self.assertFalse(z.is_alive(), "Agent must have stopped after game_over")

    def test_agent_does_not_start_if_game_over_set(self) -> None:
        """
        If game_over is already active when the agent is created,
        the run() loop must terminate immediately.
        """
        game_over.set()
        world = _make_world()
        h = Normal(pos=(0, 0), world=world)
        world.place_agent(h, (0, 0))

        h.start()
        h.join(timeout=2.0)

        self.assertFalse(h.is_alive())


class TestMilitaryAttributes(unittest.TestCase):
    """Tests for Military attributes and behavior."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()

    def test_military_force_bonus(self) -> None:
        """Military receives strength bonus from config.FORCE_MILITARY_BONUS."""
        base_force = 40
        m = Military(pos=(0, 0), world=self.world, force=base_force)
        expected = min(100, base_force + config.FORCE_MILITARY_BONUS)
        self.assertEqual(m.force, expected)

    def test_military_has_ammo(self) -> None:
        """Military has ammo attribute and can consume it."""
        m = Military(pos=(0, 0), world=self.world, ammo=5)
        self.assertEqual(m.ammo, 5)
        result = m.use_ammo()
        self.assertTrue(result)
        self.assertEqual(m.ammo, 4)

    def test_military_no_ammo(self) -> None:
        """use_ammo() returns False when there is no ammo."""
        m = Military(pos=(0, 0), world=self.world, ammo=0)
        result = m.use_ammo()
        self.assertFalse(result)

    def test_military_role(self) -> None:
        """Military has role 'military'."""
        m = Military(pos=(0, 0), world=self.world)
        self.assertEqual(m.role, "military")
        self.assertIsInstance(m, Human)


class TestScientistAttributes(unittest.TestCase):
    """Tests for Scientist attributes and behavior."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()

    def test_scientist_has_intelligence(self) -> None:
        """Scientist has intelligence attribute."""
        s = Scientist(pos=(0, 0), world=self.world, intelligence=85)
        self.assertEqual(s.intelligence, 85)

    def test_scientist_role(self) -> None:
        """Scientist has role 'scientist'."""
        s = Scientist(pos=(0, 0), world=self.world)
        self.assertEqual(s.role, "scientist")

    def test_scientist_antidote_progress(self) -> None:
        """Scientist starts with antidote progress at 0."""
        s = Scientist(pos=(0, 0), world=self.world)
        self.assertEqual(s.antidote_progress, 0)
        self.assertFalse(s.in_lab)

    def test_scientist_intelligence_clamped(self) -> None:
        """Intelligence is clamped to [0, 100]."""
        s = Scientist(pos=(0, 0), world=self.world, intelligence=150)
        self.assertEqual(s.intelligence, 100)


class TestPoliticianAttributes(unittest.TestCase):
    """Tests for Politician attributes."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()

    def test_politician_has_influence(self) -> None:
        """Politician has influence attribute."""
        p = Politician(pos=(0, 0), world=self.world, influence=90)
        self.assertEqual(p.influence, 90)

    def test_politician_role(self) -> None:
        """Politician has role 'politician'."""
        p = Politician(pos=(0, 0), world=self.world)
        self.assertEqual(p.role, "politician")

    def test_politician_high_empathy(self) -> None:
        """Politician has high empathy by default."""
        p = Politician(pos=(0, 0), world=self.world)
        self.assertGreaterEqual(p.empathy, 70)


class TestStateTransitions(unittest.TestCase):
    """Tests for state transitions."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()

    def test_valid_state_transitions(self) -> None:
        """Valid states are assigned correctly."""
        h = Normal(pos=(0, 0), world=self.world)
        for state in ("calm", "running", "fighting", "infected", "dead"):
            h.set_state(state)
            self.assertEqual(h.state, state)

    def test_invalid_state_raises(self) -> None:
        """An invalid state raises ValueError."""
        h = Normal(pos=(0, 0), world=self.world)
        with self.assertRaises(ValueError):
            h.set_state("zombie_mode")

    def test_infect_changes_state(self) -> None:
        """Human.infect() changes state to 'infected'."""
        h = Normal(pos=(0, 0), world=self.world)
        h.infect()
        self.assertEqual(h.state, "infected")

    def test_die_marks_agent_dead(self) -> None:
        """Agent.die() marks the agent as dead."""
        world = _make_world()
        h = Normal(pos=(3, 3), world=world)
        world.place_agent(h, (3, 3))
        h.die()
        self.assertFalse(h.is_alive())
        self.assertEqual(h.state, "dead")


if __name__ == "__main__":
    unittest.main()
