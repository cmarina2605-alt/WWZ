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
from typing import Dict, List, Tuple, Optional, Any, TYPE_CHECKING

import config


def _point_in_polygon(x: int, y: int, polygon: list) -> bool:
    """Ray-casting algorithm: returns True if (x, y) is inside the polygon."""
    n = len(polygon)
    inside = False
    px, py = float(x), float(y)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside

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

    # Class-level cache: avoids repeating ray-casting on every reset/batch run
    _land_cache: Dict[int, frozenset] = {}

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
        # Precomputed set of land cells — agents cannot enter ocean cells
        self.land_cells: frozenset = self._build_land_mask()
        # EventBus reference — set by Engine after construction
        self.event_bus: Optional[Any] = None
        # CommandHistory reference — set by Engine after construction
        self.command_history: Optional[Any] = None

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
        if new_pos not in self.land_cells:
            return False  # Cannot move into ocean
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

        Uses squared Euclidean distance (avoids sqrt). Takes a fast
        snapshot of the grid under the lock, then filters outside it
        to minimize lock hold time.

        Args:
            pos: Search center (x, y).
            radius: Search radius in cells.

        Returns:
            List of agents within the radius.
        """
        # Quick copy under lock — O(n) but no computation
        with self.lock:
            grid_snapshot = list(self.grid.items())

        # Filter outside lock — no contention with other threads
        r_sq = radius * radius
        px, py = pos
        results: List["Agent"] = []
        for (ax, ay), agent in grid_snapshot:
            if ax == px and ay == py:
                continue  # Skip self
            dx = ax - px
            dy = ay - py
            if dx * dx + dy * dy <= r_sq:
                results.append(agent)
        return results

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
        Finds a random free land cell in the grid.

        Uses random sampling instead of shuffling the entire land_cells
        set, which is much faster for sparse grids (300 agents on ~30k cells).

        Returns:
            Tuple (x, y) of a free land cell, or None if all are occupied.
        """
        import random
        land = list(self.land_cells)
        # Try random sampling first (fast for sparse grids)
        for _ in range(200):
            pos = random.choice(land)
            with self.lock:
                if pos not in self.grid:
                    return pos
        # Fallback: exhaustive search if grid is very crowded
        random.shuffle(land)
        with self.lock:
            for pos in land:
                if pos not in self.grid:
                    return pos
        return None

    # ------------------------------------------------------------------
    # Thread-safe snapshot for the UI
    # ------------------------------------------------------------------

    def get_state_snapshot(self) -> Dict[Tuple[int, int], Dict[str, str]]:
        """
        Returns a copy of the current grid state for rendering.

        Takes a fast snapshot of grid entries under the lock, then
        builds the detailed info dicts outside the lock to minimize
        contention with agent threads.

        Returns:
            Dict of {(x, y): {"type": str, "role": str, "state": str}}
        """
        # Quick copy under lock — just the position→agent references
        with self.lock:
            grid_copy = list(self.grid.items())

        # Build detailed snapshot outside lock
        snapshot: Dict[Tuple[int, int], Dict[str, str]] = {}
        for pos, agent in grid_copy:
            agent_type = agent.__class__.__name__
            role = getattr(agent, "role", agent_type.lower())
            info = {
                "type": agent_type,
                "role": role,
                "state": agent.state,
                "color": agent.get_color(),
            }
            # Include survival attributes if present
            if hasattr(agent, "food"):
                info["food"] = getattr(agent, "food", 100)
                info["water"] = getattr(agent, "water", 100)
            if hasattr(agent, "in_refuge"):
                info["in_refuge"] = getattr(agent, "in_refuge", False)
            if hasattr(agent, "is_president"):
                info["is_president"] = getattr(agent, "is_president", False)
            snapshot[pos] = info
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

    def _build_land_mask(self) -> frozenset:
        """
        Precomputes which grid cells fall inside the continental U.S. polygon.

        Uses ray-casting on each integer cell center. The result is cached
        at the class level so batch runs and resets don't repeat the
        expensive computation.

        Returns:
            frozenset of (x, y) tuples that are on land.
        """
        if self.size in World._land_cache:
            return World._land_cache[self.size]

        land = set()
        polygon = config.USA_POLYGON
        for x in range(self.size):
            for y in range(self.size):
                if _point_in_polygon(x, y, polygon):
                    land.add((x, y))
        result = frozenset(land)
        World._land_cache[self.size] = result
        return result

    def __repr__(self) -> str:
        return f"World(size={self.size}, agents={len(self.grid)})"
