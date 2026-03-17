"""
zombie.py — Clase Zombie para la simulación Guerra Mundial J.

En el universo de la simulación, los zombis son copias del Profe José:
resultado del experimento fallido que desató el apocalipsis.

Comportamiento por tick:
    1. El hambre (hunger) aumenta cada tick; a más hambre, más velocidad.
    2. Busca el humano vivo más cercano dentro de VISION_ZOMBIE celdas.
    3. Si lo encuentra, lo persigue (move_towards) y ataca al contacto
       (distancia ≤ 1.5): delega en combat.resolve_encounter().
    4. Si no hay humano visible, hace random walk.

Sistema de targeting:
    - Guarda target_id para mantener el objetivo entre ticks.
    - Si el objetivo desaparece (muerto, huido o fuera de rango), retargetea.

La conversión de humanos infectados NO ocurre aquí; la gestiona el
InfectionMonitor del Engine para evitar race conditions al crear nuevos threads.
"""

import random
from typing import Tuple, Optional, TYPE_CHECKING

import config
from agents.base_agent import Agent

if TYPE_CHECKING:
    from simulation.world import World
    from agents.human import Human


class Zombie(Agent):
    """
    Agente zombi que persigue y ataca humanos.

    Attributes:
        target_id (Optional[int]): ID del humano objetivo actual.
        infection_count (int): Número de humanos infectados por este zombi.
        hunger (int): Nivel de hambre (0-100); aumenta con el tiempo,
            disminuye al atacar. Afecta la velocidad de movimiento.
    """

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        force: int = 60,
        age: int = 25,
    ) -> None:
        """
        Inicializa un zombi.

        Args:
            pos: Posición inicial (x, y).
            world: Referencia al mundo compartido.
            force: Fuerza inicial del zombi (0-100).
            age: Edad aparente del zombi.
        """
        self.hunger: int = 50  # Debe inicializarse ANTES de super() (usado en _calculate_move_delay)
        super().__init__(pos=pos, world=world, force=force, age=age)
        self.target_id: Optional[int] = None
        self.infection_count: int = 0
        self.set_state("calm")

    # ------------------------------------------------------------------
    # Lógica principal
    # ------------------------------------------------------------------

    def update(self) -> None:
        """
        Lógica de actualización por tick del zombi.

        1. Aumenta el hambre ligeramente cada tick.
        2. Busca el humano más cercano en rango de visión.
        3. Si lo encuentra, persigue y ataca al contacto.
        4. Si no hay objetivo visible, hace random walk.
        """
        from simulation import movement, combat

        if not self.is_alive():
            return

        # Aumentar hambre gradualmente
        self.hunger = min(100, self.hunger + 1)

        # Recalcular velocidad según hambre
        self.move_delay = self._calculate_move_delay()

        # Buscar objetivo
        target = self._find_nearest_human()

        if target is not None:
            self.target_id = target.agent_id
            self._pursue_and_attack(target, combat, movement)
        else:
            self.target_id = None
            # Random walk
            next_pos = movement.random_walk(self.pos, self.world)
            self.world.move_agent(self, next_pos)

    def _find_nearest_human(self) -> Optional["Human"]:
        """
        Busca el humano vivo más cercano dentro del rango de visión.

        Returns:
            El agente humano más cercano, o None si no hay ninguno visible.
        """
        from agents.human import Human

        nearby = self.world.get_agents_in_radius(self.pos, config.VISION_ZOMBIE)
        humans = [
            a for a in nearby
            if isinstance(a, Human) and a.is_alive() and a.state != "infected"
        ]

        if not humans:
            return None

        return min(humans, key=lambda h: self.distance_to(h.pos))

    def _pursue_and_attack(self, target: "Human", combat, movement) -> None:
        """
        Persigue al objetivo y ataca si está en contacto.

        Args:
            target: Humano objetivo.
            combat: Módulo de combate.
            movement: Módulo de movimiento.
        """
        dist = self.distance_to(target.pos)

        if dist <= 1.5:
            # En contacto: resolver encuentro
            self.set_state("fighting")
            combat.resolve_encounter(target, self, self.world)
            self.hunger = max(0, self.hunger - 30)
            self.infection_count += 1
        else:
            # Perseguir
            self.set_state("calm")
            next_pos = movement.move_towards(self.pos, target.pos, self.world)
            self.world.move_agent(self, next_pos)

    def _calculate_move_delay(self) -> float:
        """
        Calcula el retardo de movimiento.

        Los zombis más hambrientos se mueven ligeramente más rápido.

        Returns:
            float: Segundos de espera entre ticks.
        """
        base = super()._calculate_move_delay()
        # El hambre reduce el delay (hasta 20% más rápido)
        hunger_factor = 1.0 - (self.hunger / 500.0)
        return max(0.05, base * hunger_factor)

    # ------------------------------------------------------------------
    # Representación visual
    # ------------------------------------------------------------------

    def get_color(self) -> str:
        """Retorna el color del zombi para la UI."""
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_ZOMBIE

    def __repr__(self) -> str:
        return (
            f"Zombie(id={self.agent_id}, pos={self.pos}, "
            f"target={self.target_id}, infections={self.infection_count})"
        )
