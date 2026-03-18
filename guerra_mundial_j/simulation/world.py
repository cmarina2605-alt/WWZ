"""
world.py — Shared world representation for all simulation agents.

World is the only global state of the simulation. All agents
(running in different threads) access the grid through this class,
which guarantees consistency via a threading.Lock.

Internal structure:
    grid: Dict[(x,y), Agent] — position-to-agent map; one cell,
          one agent. The lock protects all operations on it.
    tick: int — global tick counter, incremented by the Engine.
    _event_queue: List[dict] — event queue (infections, deaths,
          alerts...) consumed by the UI and optionally by the DB.

Main API:
    place_agent(agent, pos)          — places an agent (fails if cell occupied).
    move_agent(agent, new_pos)       — moves atomically (fails if occupied).
    remove_agent(agent)              — removes from the grid (on death).
    get_agents_in_radius(pos, r)     — list of agents within a given radius.
    get_state_snapshot()             — thread-safe copy for rendering the UI.
    push_event / pop_events          — event queue for the EventLog and DB.

Design note: methods acquire the lock internally, so external callers
do NOT need to do so except for compound operations requiring atomicity.
"""

import threading
import math
from typing import Dict, List, Tuple, Optional, Any, TYPE_CHECKING

import config

if TYPE_CHECKING:
    from agents.base_agent import Agent


class World:
    """
    Simulation world: 2D grid shared across threads.

    Grid access is synchronized with a global threading.Lock
    named `lock`. The methods of this class acquire the lock
    internally, so callers do not need to do so
    (except for compound operations requiring atomicity).

    Attributes:
        size (int): Side length of the square grid.
        lock (threading.Lock): Global lock to protect the grid.
        grid (Dict[Tuple[int,int], Agent]): Position-to-agent map.
        tick (int): Global tick counter (incremented by Engine).
    """

    def __init__(self, size: int = config.GRID_SIZE) -> None:
        """
        Initializes the world with an empty grid.

        Args:
            size: Side of the square grid (cells).
        """
        self.size: int = size
        self.lock: threading.Lock = threading.Lock()
        self.grid: Dict[Tuple[int, int], "Agent"] = {}
        self.tick: int = 0
        self._event_queue: List[Dict[str, Any]] = []
        self._event_lock: threading.Lock = threading.Lock()
        # Active strategy: "none" until the White House responds
        # All agents read from here to modulate their behavior
        self.strategy: str = "none"

    # ------------------------------------------------------------------
    # Grid operations
    # ------------------------------------------------------------------

    def place_agent(self, agent: "Agent", pos: Tuple[int, int]) -> bool:
        """
        Places an agent at a grid position.

        Args:
            agent: Agent to place.
            pos: Target position (x, y).

        Returns:
            bool: True if placed successfully, False if the cell was occupied.
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
        Moves an agent to a new position.

        Removes the agent from its current position and places it at new_pos.
        If new_pos is occupied, the move is not performed.

        Args:
            agent: Agent to move.
            new_pos: New position (x, y).

        Returns:
            bool: True if the move was successful.
        """
        new_pos = self._clamp(new_pos)
        with self.lock:
            # Verify that the destination cell is free
            if new_pos in self.grid and self.grid[new_pos] is not agent:
                return False
            # Remove from current position
            old_pos = agent.pos
            if old_pos in self.grid and self.grid[old_pos] is agent:
                del self.grid[old_pos]
            # Place at new position
            self.grid[new_pos] = agent
            agent.pos = new_pos
            return True

    def remove_agent(self, agent: "Agent") -> None:
        """
        Removes an agent from the grid.

        Args:
            agent: Agent to remove.
        """
        with self.lock:
            if agent.pos in self.grid and self.grid[agent.pos] is agent:
                del self.grid[agent.pos]

    def get_agents_in_radius(
        self, pos: Tuple[int, int], radius: float
    ) -> List["Agent"]:
        """
        Returns all agents within a given radius.

        Uses Euclidean distance. Does not include the agent at the
        exact position of pos (if it is the one asking).

        Args:
            pos: Search center (x, y).
            radius: Search radius in cells.

        Returns:
            List of agents within the radius.
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
        Returns the agent at an exact position, or None.

        Args:
            pos: Position (x, y) to query.

        Returns:
            Agent at that position or None.
        """
        with self.lock:
            return self.grid.get(pos)

    def is_cell_free(self, pos: Tuple[int, int]) -> bool:
        """
        Checks whether a cell is free (without external lock).

        Args:
            pos: Position to check.

        Returns:
            bool: True if the cell is free.
        """
        with self.lock:
            return pos not in self.grid

    def find_free_cell(self) -> Optional[Tuple[int, int]]:
        """
        Finds a random free cell in the grid.

        Returns:
            Tuple (x, y) of a free cell, or None if the grid is full.
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
    # Thread-safe snapshot for the UI
    # ------------------------------------------------------------------

    def get_state_snapshot(self) -> Dict[Tuple[int, int], Dict[str, str]]:
        """
        Returns a copy of the current grid state for rendering.

        The copy is made under the lock to guarantee consistency.
        The result can be read without the lock once obtained.

        Returns:
            Dict of {(x, y): {"type": str, "role": str, "state": str}}
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
    # World events
    # ------------------------------------------------------------------

    def push_event(self, event_type: str, description: str) -> None:
        """
        Records an event in the world's event queue.

        Events are consumed by the UI's EventLog and by
        the database.

        Args:
            event_type: Type of event (e.g. "infection", "death", "antidote").
            description: Human-readable description of the event.
        """
        with self._event_lock:
            self._event_queue.append({
                "tick": self.tick,
                "type": event_type,
                "description": description,
            })

    def pop_events(self) -> List[Dict[str, Any]]:
        """
        Extracts and returns all pending events.

        Returns:
            List of event dicts. Empty if there are no new events.
        """
        with self._event_lock:
            events = self._event_queue.copy()
            self._event_queue.clear()
        return events

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _clamp(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """
        Ensures a position is within the grid boundaries.

        Args:
            pos: Position (x, y) potentially out of range.

        Returns:
            Position clamped within [0, size-1].
        """
        x = max(0, min(self.size - 1, pos[0]))
        y = max(0, min(self.size - 1, pos[1]))
        return (x, y)

    def count_agents_by_type(self) -> Dict[str, int]:
        """
        Counts agents by type (Zombie, Human, etc.).

        Returns:
            Dict of {type: count}.
        """
        counts: Dict[str, int] = {}
        with self.lock:
            for agent in self.grid.values():
                t = agent.__class__.__name__
                counts[t] = counts.get(t, 0) + 1
        return counts

    def __repr__(self) -> str:
        return f"World(size={self.size}, agents={len(self.grid)})"
