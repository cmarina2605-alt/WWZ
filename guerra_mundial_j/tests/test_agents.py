"""
test_agents.py — Tests unitarios para agentes (Human y Zombie).

Cubre:
    - Instanciación correcta de Human y Zombie.
    - Respeto de game_over en el bucle run().
    - Herencia y atributos de Military, Scientist y Politician.
    - Transiciones de estado válidas.
"""

import threading
import time
import unittest

# Asegurar que los imports del proyecto funcionen
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from agents.base_agent import game_over, antidote_ready, national_alert, _generate_id
from agents.human import Human, Normal, Scientist, Military, Politician
from agents.zombie import Zombie
from simulation.world import World


def _make_world() -> World:
    """Crea un World de tamaño reducido para tests."""
    return World(size=20)


def _place(agent, world: World) -> None:
    """Coloca un agente en el mundo (encuentra celda libre)."""
    pos = world.find_free_cell()
    assert pos is not None
    world.place_agent(agent, pos)


class TestAgentInstantiation(unittest.TestCase):
    """Tests de instanciación básica."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()  # Detener cualquier thread vivo

    def test_human_normal_instantiation(self) -> None:
        """Normal se instancia con los atributos correctos."""
        h = Normal(pos=(0, 0), world=self.world, force=60, age=25)
        self.assertEqual(h.role, "normal")
        self.assertEqual(h.force, 60)
        self.assertEqual(h.age, 25)
        self.assertEqual(h.state, "calm")
        self.assertIsNotNone(h.agent_id)
        self.assertIsInstance(h, Human)

    def test_zombie_instantiation(self) -> None:
        """Zombie se instancia con atributos correctos."""
        z = Zombie(pos=(5, 5), world=self.world, force=70)
        self.assertEqual(z.state, "calm")
        self.assertIsNone(z.target_id)
        self.assertEqual(z.infection_count, 0)
        self.assertIsInstance(z, Zombie)

    def test_unique_ids(self) -> None:
        """Cada agente tiene un ID único."""
        w = _make_world()
        agents = [Normal(pos=(i, 0), world=w) for i in range(5)]
        ids = [a.agent_id for a in agents]
        self.assertEqual(len(ids), len(set(ids)), "IDs deben ser únicos")

    def test_force_clamped(self) -> None:
        """La fuerza se clampea a [0, 100]."""
        h1 = Normal(pos=(0, 0), world=self.world, force=200)
        h2 = Normal(pos=(1, 0), world=self.world, force=-50)
        self.assertEqual(h1.force, 100)
        self.assertEqual(h2.force, 0)


class TestGameOverRespect(unittest.TestCase):
    """Tests de respeto al evento game_over en el bucle run()."""

    def setUp(self) -> None:
        game_over.clear()
        antidote_ready.clear()
        national_alert.clear()

    def test_agent_stops_when_game_over(self) -> None:
        """
        El agente debe detenerse al activar game_over.

        El thread debe terminar en menos de 2 segundos tras activar game_over.
        """
        world = _make_world()
        z = Zombie(pos=(0, 0), world=world)
        world.place_agent(z, (0, 0))

        z.start()
        self.assertTrue(z.is_alive())

        game_over.set()
        z.join(timeout=2.0)

        self.assertFalse(z.is_alive(), "El agente debe haber terminado tras game_over")

    def test_agent_does_not_start_if_game_over_set(self) -> None:
        """
        Si game_over ya está activo al crear el agente, el bucle run()
        debe terminar inmediatamente.
        """
        game_over.set()
        world = _make_world()
        h = Normal(pos=(0, 0), world=world)
        world.place_agent(h, (0, 0))

        h.start()
        h.join(timeout=2.0)

        self.assertFalse(h.is_alive())


class TestMilitaryAttributes(unittest.TestCase):
    """Tests de atributos y comportamiento de Military."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()

    def test_military_force_bonus(self) -> None:
        """Military recibe bonus de fuerza de config.FORCE_MILITARY_BONUS."""
        base_force = 40
        m = Military(pos=(0, 0), world=self.world, force=base_force)
        expected = min(100, base_force + config.FORCE_MILITARY_BONUS)
        self.assertEqual(m.force, expected)

    def test_military_has_ammo(self) -> None:
        """Military tiene atributo ammo y puede consumirlo."""
        m = Military(pos=(0, 0), world=self.world, ammo=5)
        self.assertEqual(m.ammo, 5)
        result = m.use_ammo()
        self.assertTrue(result)
        self.assertEqual(m.ammo, 4)

    def test_military_no_ammo(self) -> None:
        """use_ammo() retorna False cuando no hay munición."""
        m = Military(pos=(0, 0), world=self.world, ammo=0)
        result = m.use_ammo()
        self.assertFalse(result)

    def test_military_role(self) -> None:
        """Military tiene rol 'military'."""
        m = Military(pos=(0, 0), world=self.world)
        self.assertEqual(m.role, "military")
        self.assertIsInstance(m, Human)


class TestScientistAttributes(unittest.TestCase):
    """Tests de atributos y comportamiento de Scientist."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()

    def test_scientist_has_intelligence(self) -> None:
        """Scientist tiene atributo intelligence."""
        s = Scientist(pos=(0, 0), world=self.world, intelligence=85)
        self.assertEqual(s.intelligence, 85)

    def test_scientist_role(self) -> None:
        """Scientist tiene rol 'scientist'."""
        s = Scientist(pos=(0, 0), world=self.world)
        self.assertEqual(s.role, "scientist")

    def test_scientist_antidote_progress(self) -> None:
        """Scientist comienza con progreso de antídoto en 0."""
        s = Scientist(pos=(0, 0), world=self.world)
        self.assertEqual(s.antidote_progress, 0)
        self.assertFalse(s.in_lab)

    def test_scientist_intelligence_clamped(self) -> None:
        """La inteligencia se clampea a [0, 100]."""
        s = Scientist(pos=(0, 0), world=self.world, intelligence=150)
        self.assertEqual(s.intelligence, 100)


class TestPoliticianAttributes(unittest.TestCase):
    """Tests de atributos de Politician."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()

    def test_politician_has_influence(self) -> None:
        """Politician tiene atributo influence."""
        p = Politician(pos=(0, 0), world=self.world, influence=90)
        self.assertEqual(p.influence, 90)

    def test_politician_role(self) -> None:
        """Politician tiene rol 'politician'."""
        p = Politician(pos=(0, 0), world=self.world)
        self.assertEqual(p.role, "politician")

    def test_politician_high_empathy(self) -> None:
        """Politician tiene empatía alta por defecto."""
        p = Politician(pos=(0, 0), world=self.world)
        self.assertGreaterEqual(p.empathy, 70)


class TestStateTransitions(unittest.TestCase):
    """Tests de transiciones de estado."""

    def setUp(self) -> None:
        game_over.clear()
        self.world = _make_world()

    def tearDown(self) -> None:
        game_over.set()

    def test_valid_state_transitions(self) -> None:
        """Los estados válidos se asignan correctamente."""
        h = Normal(pos=(0, 0), world=self.world)
        for state in ("calm", "running", "fighting", "infected", "dead"):
            h.set_state(state)
            self.assertEqual(h.state, state)

    def test_invalid_state_raises(self) -> None:
        """Un estado inválido lanza ValueError."""
        h = Normal(pos=(0, 0), world=self.world)
        with self.assertRaises(ValueError):
            h.set_state("zombie_mode")

    def test_infect_changes_state(self) -> None:
        """Human.infect() cambia el estado a 'infected'."""
        h = Normal(pos=(0, 0), world=self.world)
        h.infect()
        self.assertEqual(h.state, "infected")

    def test_die_marks_agent_dead(self) -> None:
        """Agent.die() marca al agente como muerto."""
        world = _make_world()
        h = Normal(pos=(3, 3), world=world)
        world.place_agent(h, (3, 3))
        h.die()
        self.assertFalse(h.is_alive())
        self.assertEqual(h.state, "dead")


if __name__ == "__main__":
    unittest.main()
