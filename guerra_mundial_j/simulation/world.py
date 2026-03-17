"""
world.py — Representación del mundo compartido entre todos los agentes.

El grid es un diccionario {(x, y): Agent} protegido por un
threading.Lock global. Todas las operaciones de lectura/escritura
sobre el grid deben adquirir este lock.
"""

import threading
import math
from typing import Dict, List, Tuple, Optional, Any, TYPE_CHECKING

import config

if TYPE_CHECKING:
    from agents.base_agent import Agent


class World:
    """
    Mundo de la simulación: grid 2D compartido entre threads.

    El acceso al grid se sincroniza con un threading.Lock global
    llamado `lock`. Los métodos de esta clase adquieren el lock
    internamente, por lo que los llamadores no necesitan hacerlo
    (excepto para operaciones compuestas que requieran atomicidad).

    Attributes:
        size (int): Tamaño del lado del grid cuadrado.
        lock (threading.Lock): Lock global para proteger el grid.
        grid (Dict[Tuple[int,int], Agent]): Mapa de posición a agente.
        tick (int): Contador de ticks globales (incrementado por Engine).
    """

    def __init__(self, size: int = config.GRID_SIZE) -> None:
        """
        Inicializa el mundo con un grid vacío.

        Args:
            size: Lado del grid cuadrado (celdas).
        """
        self.size: int = size
        self.lock: threading.Lock = threading.Lock()
        self.grid: Dict[Tuple[int, int], "Agent"] = {}
        self.tick: int = 0
        self._event_queue: List[Dict[str, Any]] = []
        self._event_lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Operaciones sobre el grid
    # ------------------------------------------------------------------

    def place_agent(self, agent: "Agent", pos: Tuple[int, int]) -> bool:
        """
        Coloca un agente en una posición del grid.

        Args:
            agent: Agente a colocar.
            pos: Posición (x, y) objetivo.

        Returns:
            bool: True si se colocó correctamente, False si la celda estaba ocupada.
        """
        pos = self._clamp(pos)
        with self.lock:
            if pos in self.grid:
                return False
            self.grid[pos] = agent
            agent.pos = pos
            return True

    def move_agent(self, agent: "Agent", new_pos: Tuple[int, int]) -> bool:
        """
        Mueve un agente a una nueva posición.

        Elimina al agente de su posición actual y lo coloca en new_pos.
        Si new_pos está ocupada, no se realiza el movimiento.

        Args:
            agent: Agente a mover.
            new_pos: Nueva posición (x, y).

        Returns:
            bool: True si el movimiento fue exitoso.
        """
        new_pos = self._clamp(new_pos)
        with self.lock:
            # Verificar que la celda destino está libre
            if new_pos in self.grid and self.grid[new_pos] is not agent:
                return False
            # Eliminar de posición actual
            old_pos = agent.pos
            if old_pos in self.grid and self.grid[old_pos] is agent:
                del self.grid[old_pos]
            # Colocar en nueva posición
            self.grid[new_pos] = agent
            agent.pos = new_pos
            return True

    def remove_agent(self, agent: "Agent") -> None:
        """
        Elimina un agente del grid.

        Args:
            agent: Agente a eliminar.
        """
        with self.lock:
            if agent.pos in self.grid and self.grid[agent.pos] is agent:
                del self.grid[agent.pos]

    def get_agents_in_radius(
        self, pos: Tuple[int, int], radius: float
    ) -> List["Agent"]:
        """
        Retorna todos los agentes dentro de un radio dado.

        Utiliza distancia euclidiana. No incluye al agente en la
        posición exacta de pos (si es el mismo que pregunta).

        Args:
            pos: Centro de búsqueda (x, y).
            radius: Radio de búsqueda en celdas.

        Returns:
            Lista de agentes dentro del radio.
        """
        results: List["Agent"] = []
        with self.lock:
            for (ax, ay), agent in self.grid.items():
                dx = ax - pos[0]
                dy = ay - pos[1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist <= radius and agent.pos != pos:
                    results.append(agent)
        return results

    def get_agent_at(self, pos: Tuple[int, int]) -> Optional["Agent"]:
        """
        Retorna el agente en una posición exacta, o None.

        Args:
            pos: Posición (x, y) a consultar.

        Returns:
            Agente en esa posición o None.
        """
        with self.lock:
            return self.grid.get(pos)

    def is_cell_free(self, pos: Tuple[int, int]) -> bool:
        """
        Comprueba si una celda está libre (sin lock externo).

        Args:
            pos: Posición a comprobar.

        Returns:
            bool: True si la celda está libre.
        """
        with self.lock:
            return pos not in self.grid

    def find_free_cell(self) -> Optional[Tuple[int, int]]:
        """
        Busca una celda libre aleatoria en el grid.

        Returns:
            Tupla (x, y) de una celda libre, o None si el grid está lleno.
        """
        import random
        attempts = 0
        max_attempts = self.size * self.size
        with self.lock:
            while attempts < max_attempts:
                x = random.randint(0, self.size - 1)
                y = random.randint(0, self.size - 1)
                if (x, y) not in self.grid:
                    return (x, y)
                attempts += 1
        return None

    # ------------------------------------------------------------------
    # Snapshot thread-safe para la UI
    # ------------------------------------------------------------------

    def get_state_snapshot(self) -> Dict[Tuple[int, int], Dict[str, str]]:
        """
        Retorna una copia del estado actual del grid para renderizado.

        La copia se hace bajo el lock para garantizar consistencia.
        El resultado puede leerse sin lock una vez obtenido.

        Returns:
            Dict de {(x, y): {"type": str, "role": str, "state": str}}
        """
        snapshot: Dict[Tuple[int, int], Dict[str, str]] = {}
        with self.lock:
            for pos, agent in self.grid.items():
                agent_type = agent.__class__.__name__
                role = getattr(agent, "role", agent_type.lower())
                snapshot[pos] = {
                    "type": agent_type,
                    "role": role,
                    "state": agent.state,
                    "color": agent.get_color(),
                }
        return snapshot

    # ------------------------------------------------------------------
    # Eventos del mundo
    # ------------------------------------------------------------------

    def push_event(self, event_type: str, description: str) -> None:
        """
        Registra un evento en la cola de eventos del mundo.

        Los eventos son consumidos por el EventLog de la UI y por
        la base de datos.

        Args:
            event_type: Tipo de evento (e.g. "infection", "death", "antidote").
            description: Descripción legible del evento.
        """
        with self._event_lock:
            self._event_queue.append({
                "tick": self.tick,
                "type": event_type,
                "description": description,
            })

    def pop_events(self) -> List[Dict[str, Any]]:
        """
        Extrae y retorna todos los eventos pendientes.

        Returns:
            Lista de dicts de eventos. Vacía si no hay eventos nuevos.
        """
        with self._event_lock:
            events = self._event_queue.copy()
            self._event_queue.clear()
        return events

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    def _clamp(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """
        Asegura que una posición está dentro de los límites del grid.

        Args:
            pos: Posición (x, y) potencialmente fuera de rango.

        Returns:
            Posición clampeada dentro de [0, size-1].
        """
        x = max(0, min(self.size - 1, pos[0]))
        y = max(0, min(self.size - 1, pos[1]))
        return (x, y)

    def count_agents_by_type(self) -> Dict[str, int]:
        """
        Cuenta agentes por tipo (Zombie, Human, etc.).

        Returns:
            Dict de {tipo: count}.
        """
        counts: Dict[str, int] = {}
        with self.lock:
            for agent in self.grid.values():
                t = agent.__class__.__name__
                counts[t] = counts.get(t, 0) + 1
        return counts

    def __repr__(self) -> str:
        return f"World(size={self.size}, agents={len(self.grid)})"
