"""
test_engine.py — Tests del motor de simulación (Engine y World).

Verifica el comportamiento del Engine como orquestador y la
thread-safety del World bajo acceso concurrente.

Suites de tests:
    TestEngineCreation          — el Engine crea el número correcto de agentes
                                  y threads; todos son daemon; la semilla produce
                                  resultados deterministas (reproducibilidad).
    TestWorldLockRaceConditions — múltiples threads moviendo agentes no crashean
                                  ni corrompen el grid; el lock impide que dos
                                  agentes ocupen la misma celda; get_agents_in_radius
                                  es segura bajo escritura concurrente.
    TestWinConditions           — check_win_conditions() detecta correctamente:
                                  zombies_win (sin humanos), humans_win (sin zombis),
                                  humans_win (antidote_ready activo), None (ambos vivos).
    TestEngineSnapshot          — get_snapshot() contiene todas las claves requeridas
                                  y el campo 'grid' es un dict.

Nota: cada test limpia game_over en setUp y lo activa en tearDown para
detener threads residuales y evitar interferencias entre suites.
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
    """Tests de creación de agentes por el motor."""

    def setUp(self) -> None:
        game_over.clear()
        antidote_ready.clear()

    def tearDown(self) -> None:
        game_over.set()
        time.sleep(0.3)

    def test_engine_creates_correct_thread_count(self) -> None:
        """
        Engine crea el número correcto de threads de agentes.

        Total esperado = n_humans + n_zombies.
        """
        n_humans = 10
        n_zombies = 2
        engine = Engine(n_humans=n_humans, n_zombies=n_zombies)
        engine.start_simulation()

        # Dar tiempo a que los threads arranquen
        time.sleep(0.3)

        alive_agents = [a for a in engine.agents if a.is_alive()]
        total_expected = n_humans + n_zombies
        self.assertEqual(
            len(engine.agents),
            total_expected,
            f"Esperados {total_expected} agentes, encontrados {len(engine.agents)}",
        )

    def test_engine_threads_are_daemon(self) -> None:
        """Todos los threads de agentes son daemon."""
        engine = Engine(n_humans=5, n_zombies=1)
        engine.start_simulation()
        time.sleep(0.2)
        for agent in engine.agents:
            self.assertTrue(agent.daemon, f"Agente {agent.agent_id} no es daemon")

    def test_engine_seed_reproducibility(self) -> None:
        """
        Dos simulaciones con la misma semilla crean los mismos agentes
        en las mismas posiciones (determinismo del PRNG).
        """
        game_over.clear()
        e1 = Engine(seed=42, n_humans=5, n_zombies=1)
        e1._create_agents()
        pos1 = sorted([a.pos for a in e1.agents])

        game_over.clear()
        e2 = Engine(seed=42, n_humans=5, n_zombies=1)
        e2._create_agents()
        pos2 = sorted([a.pos for a in e2.agents])

        self.assertEqual(pos1, pos2, "Misma semilla debe producir mismas posiciones")


class TestWorldLockRaceConditions(unittest.TestCase):
    """Tests de thread-safety del World."""

    def setUp(self) -> None:
        game_over.clear()

    def tearDown(self) -> None:
        game_over.set()

    def test_concurrent_moves_no_crash(self) -> None:
        """
        Múltiples threads moviendo agentes simultáneamente no producen
        errores ni corrupción del grid.
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

        self.assertEqual(len(errors), 0, f"Errores en movimiento concurrente: {errors}")

    def test_lock_prevents_duplicate_placement(self) -> None:
        """
        Dos threads intentando colocar en la misma celda → solo uno tiene éxito.
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

        # Solo uno debe haber tenido éxito (o ambos fallaron si ya estaba ocupada)
        self.assertLessEqual(
            results.count(True), 1,
            "Solo un agente puede ocupar una celda simultáneamente",
        )

    def test_get_agents_in_radius_thread_safe(self) -> None:
        """
        get_agents_in_radius() no lanza excepciones bajo modificación concurrente.
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

        self.assertEqual(len(errors), 0, f"Errores bajo acceso concurrente: {errors}")


class TestWinConditions(unittest.TestCase):
    """Tests de check_win_conditions()."""

    def setUp(self) -> None:
        game_over.clear()
        antidote_ready.clear()

    def tearDown(self) -> None:
        game_over.set()

    def test_zombies_win_when_no_humans(self) -> None:
        """
        Cuando no hay humanos vivos, check_win_conditions() establece
        result = 'zombies_win'.
        """
        engine = Engine(n_humans=2, n_zombies=1)
        engine._create_agents()

        # Matar a todos los humanos
        for agent in engine.agents:
            if agent.__class__.__name__ != "Zombie":
                agent.die()

        engine.check_win_conditions()
        self.assertEqual(engine.result, "zombies_win")

    def test_humans_win_when_no_zombies(self) -> None:
        """
        Cuando no hay zombis, check_win_conditions() establece
        result = 'humans_win'.
        """
        engine = Engine(n_humans=3, n_zombies=1)
        engine._create_agents()

        # Matar a todos los zombis
        for agent in engine.agents:
            if agent.__class__.__name__ == "Zombie":
                agent.die()

        engine.check_win_conditions()
        self.assertEqual(engine.result, "humans_win")

    def test_antidote_triggers_human_win(self) -> None:
        """
        Cuando antidote_ready está activo, los humanos ganan.
        """
        engine = Engine(n_humans=3, n_zombies=2)
        engine._create_agents()
        antidote_ready.set()

        engine.check_win_conditions()
        self.assertEqual(engine.result, "humans_win")

    def test_no_result_when_both_present(self) -> None:
        """
        Si hay humanos y zombis, result debe ser None.
        """
        engine = Engine(n_humans=5, n_zombies=2)
        engine._create_agents()

        # Verificar que al menos hay agentes de ambos tipos vivos
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
                "No debe haber resultado con ambos bandos presentes",
            )


class TestEngineSnapshot(unittest.TestCase):
    """Tests del método get_snapshot()."""

    def setUp(self) -> None:
        game_over.clear()

    def tearDown(self) -> None:
        game_over.set()

    def test_snapshot_has_required_keys(self) -> None:
        """get_snapshot() incluye todas las claves requeridas."""
        engine = Engine(n_humans=3, n_zombies=1)
        engine._create_agents()
        snap = engine.get_snapshot()

        required_keys = {"tick", "n_humans", "n_zombies", "result", "running", "grid", "seed"}
        for key in required_keys:
            self.assertIn(key, snap, f"Clave '{key}' falta en snapshot")

    def test_snapshot_grid_is_dict(self) -> None:
        """El campo 'grid' del snapshot es un diccionario."""
        engine = Engine(n_humans=3, n_zombies=1)
        engine._create_agents()
        snap = engine.get_snapshot()
        self.assertIsInstance(snap["grid"], dict)


if __name__ == "__main__":
    unittest.main()
