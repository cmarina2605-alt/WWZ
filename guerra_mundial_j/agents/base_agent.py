"""
base_agent.py — Clase abstracta base para todos los agentes de la simulación.

Cada agente es un threading.Thread cuyo bucle de vida está en run().
Las subclases deben implementar update() y get_color().
"""

import threading
import time
import math
from abc import ABC, abstractmethod
from typing import Tuple, Optional, TYPE_CHECKING

import config

if TYPE_CHECKING:
    from simulation.world import World

# Señales globales compartidas por toda la simulación
game_over: threading.Event = threading.Event()
antidote_ready: threading.Event = threading.Event()
national_alert: threading.Event = threading.Event()

# Contador atómico de IDs
_id_lock = threading.Lock()
_next_id: int = 0


def _generate_id() -> int:
    """Genera un ID único y thread-safe para cada agente."""
    global _next_id
    with _id_lock:
        _next_id += 1
        return _next_id


class Agent(threading.Thread, ABC):
    """
    Clase abstracta que representa un agente de la simulación.

    Hereda de threading.Thread; el método run() es el bucle de vida
    del agente. Cada tick llama a self.update() y luego duerme
    move_delay segundos.

    Attributes:
        agent_id (int): Identificador único del agente.
        pos (Tuple[int, int]): Posición (x, y) en el grid.
        force (int): Fuerza física del agente (0-100).
        age (int): Edad del agente (afecta move_delay y combate).
        state (str): Estado actual: calm | running | fighting | infected | dead.
        world (World): Referencia al mundo compartido.
        move_delay (float): Segundos entre cada actualización del agente.
    """

    VALID_STATES = {"calm", "running", "fighting", "infected", "dead"}

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        force: int = 50,
        age: int = 30,
    ) -> None:
        """
        Inicializa el agente con posición, fuerza y edad.

        Args:
            pos: Posición inicial (x, y) en el grid.
            world: Referencia al objeto World compartido.
            force: Fuerza física inicial (0-100).
            age: Edad inicial del agente.
        """
        super().__init__(daemon=True)
        self.agent_id: int = _generate_id()
        self.pos: Tuple[int, int] = pos
        self.world: "World" = world
        self.force: int = max(0, min(100, force))
        self.age: int = age
        self.state: str = "calm"
        self.move_delay: float = self._calculate_move_delay()
        self._alive: bool = True

    # ------------------------------------------------------------------
    # Thread lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Bucle de vida del agente.

        Ejecuta update() cada move_delay segundos hasta que game_over
        se active o el agente muera.
        """
        while not game_over.is_set() and self._alive:
            if self.state == "dead":
                break
            try:
                self.update()
            except Exception as exc:
                # Evitar que un error en un agente derribe el thread principal
                print(f"[Agent {self.agent_id}] Error en update(): {exc}")
            time.sleep(self.move_delay)
        # Marcar como inactivo al salir del bucle (por game_over o muerte)
        self._alive = False

    def die(self) -> None:
        """Marca al agente como muerto y detiene su bucle."""
        self.state = "dead"
        self._alive = False
        self.world.remove_agent(self)

    # ------------------------------------------------------------------
    # Métodos de estado
    # ------------------------------------------------------------------

    def set_state(self, new_state: str) -> None:
        """
        Cambia el estado del agente con validación.

        Args:
            new_state: Nuevo estado. Debe pertenecer a VALID_STATES.

        Raises:
            ValueError: Si new_state no es un estado válido.
        """
        if new_state not in self.VALID_STATES:
            raise ValueError(f"Estado inválido: '{new_state}'. Válidos: {self.VALID_STATES}")
        self.state = new_state

    def is_alive(self) -> bool:
        """Retorna True si el agente no está muerto."""
        return self.state != "dead" and self._alive

    # ------------------------------------------------------------------
    # Cálculo de velocidad
    # ------------------------------------------------------------------

    def _calculate_move_delay(self) -> float:
        """
        Calcula el retardo entre movimientos según edad y fuerza.

        Agentes más jóvenes y fuertes se mueven más rápido.

        Returns:
            float: Segundos de espera entre ticks.
        """
        # Penalización por edad
        age_factor = 1.0
        if self.age > config.AGE_PENALTY_THRESHOLD:
            age_factor = 1.0 + (self.age - config.AGE_PENALTY_THRESHOLD) * 0.02

        # Bonificación por fuerza
        force_factor = 1.0 - (self.force / 200.0)  # hasta 50% más rápido

        delay = config.TICK_SPEED * age_factor * (0.5 + force_factor)
        return max(0.05, delay)

    # ------------------------------------------------------------------
    # Distancia utilitaria
    # ------------------------------------------------------------------

    def distance_to(self, other_pos: Tuple[int, int]) -> float:
        """
        Calcula la distancia euclidiana a otra posición.

        Args:
            other_pos: Posición (x, y) de destino.

        Returns:
            float: Distancia en celdas.
        """
        dx = self.pos[0] - other_pos[0]
        dy = self.pos[1] - other_pos[1]
        return math.sqrt(dx * dx + dy * dy)

    # ------------------------------------------------------------------
    # Métodos abstractos que las subclases deben implementar
    # ------------------------------------------------------------------

    @abstractmethod
    def update(self) -> None:
        """
        Lógica de actualización por tick.

        Cada subclase define aquí su comportamiento: movimiento,
        detección de amenazas, combate, etc.
        """
        ...

    @abstractmethod
    def get_color(self) -> str:
        """
        Retorna el color de representación en la UI.

        Returns:
            str: Color compatible con Tkinter (e.g. "red", "#ff0000").
        """
        ...

    # ------------------------------------------------------------------
    # Representación
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.agent_id}, "
            f"pos={self.pos}, state={self.state}, force={self.force})"
        )
