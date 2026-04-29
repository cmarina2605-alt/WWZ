"""
base_agent.py — Abstract base class for all simulation agents.

Defines the common lifecycle of any world entity (human or zombie):
starting the thread, executing update() every move_delay seconds and stopping
when game_over is set or the agent dies.

Design Patterns used:
    - Template Method: run() defines the skeleton algorithm; subclasses
      fill in update() and get_color().
    - Signals: uses module-level threading.Event objects from signals.py.

Responsibilities of this class:
    - Thread-safe unique ID generation for each agent.
    - run() loop: calls update(), sleeps move_delay and repeats.
    - move_delay calculation based on age and force.
    - Valid states: calm | running | fighting | infected | dead.

Subclasses must implement:
    update()    — tick decision logic (movement, combat...).
    get_color() — representation color in the Tkinter UI.
"""

import threading
import time
import math
from abc import ABC, abstractmethod
from typing import Tuple, Optional, TYPE_CHECKING

import config
from signals import game_over, antidote_ready, national_alert, pause_event

if TYPE_CHECKING:
    from simulation.world import World

# Atomic ID counter
_id_lock = threading.Lock()
_next_id: int = 0


def _generate_id() -> int:
    """Generates a unique, thread-safe ID for each agent."""
    global _next_id
    with _id_lock:
        _next_id += 1
        return _next_id


class Agent(threading.Thread, ABC):
    """
    Abstract class representing a simulation agent.

    Inherits from threading.Thread; the run() method is the agent's
    life loop. Each tick calls self.update() and then sleeps move_delay seconds.

    Attributes:
        agent_id (int): Unique agent identifier.
        pos (Tuple[int, int]): Position (x, y) in the grid.
        force (int): Physical force of the agent (0-100).
        age (int): Agent age (affects move_delay and combat).
        state (str): Current state: calm | running | fighting | infected | dead.
        world (World): Reference to the shared world.
        move_delay (float): Seconds between each agent update.
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
        Initializes the agent with position, force and age.

        Args:
            pos: Initial position (x, y) in the grid.
            world: Reference to the shared World object.
            force: Initial physical force (0-100).
            age: Initial agent age.
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
        Agent life loop.

        Executes update() every move_delay seconds until game_over
        is set or the agent dies.
        """
        while not game_over.is_set() and self._alive:
            # Use timeout so we can re-check game_over even while paused
            pause_event.wait(timeout=0.5)
            if game_over.is_set() or not self._alive:
                break
            if not pause_event.is_set():
                continue  # Still paused — loop back and wait again
            if self.state == "dead":
                break
            try:
                self.update()
            except Exception as exc:
                print(f"[Agent {self.agent_id}] Error in update(): {exc}")
            time.sleep(self.move_delay)
        # Mark as inactive when exiting the loop (due to game_over or death)
        self._alive = False

    def die(self) -> None:
        """Marks the agent as dead and stops its loop."""
        self.state = "dead"
        self._alive = False
        self.world.remove_agent(self)

    # ------------------------------------------------------------------
    # State methods
    # ------------------------------------------------------------------

    def set_state(self, new_state: str) -> None:
        """
        Changes the agent's state with validation.

        Infected agents can only transition to "dead" — all other
        state changes are silently ignored so the incubation period
        is never cancelled by fear updates, panic spread, or combat.

        Args:
            new_state: New state. Must belong to VALID_STATES.

        Raises:
            ValueError: If new_state is not a valid state.
        """
        if new_state not in self.VALID_STATES:
            raise ValueError(f"Invalid state: '{new_state}'. Valid states: {self.VALID_STATES}")
        if self.state == "infected" and new_state != "dead":
            return
        self.state = new_state

    def is_alive(self) -> bool:
        """Returns True if the agent is not dead."""
        return self.state != "dead" and self._alive

    # ------------------------------------------------------------------
    # Speed calculation
    # ------------------------------------------------------------------

    def _calculate_move_delay(self) -> float:
        """
        Calculates the movement delay based on age and force.

        Younger and stronger agents move faster.

        Formula:
            base = TICK_SPEED (0.1s)
            age_factor: 1.0 for age ≤ 60, scales up to ~1.8 for age 100
                        (elderly move up to 80% slower)
            force_bonus: force/100 gives 0–1, mapped to 0.6–1.0 multiplier
                         (strongest agents move 40% faster than weakest)
            delay = base × age_factor × force_multiplier

        Returns:
            float: Wait seconds between ticks.
        """
        # Age penalty: gradual slowdown past threshold
        age_factor = 1.0
        if self.age > config.AGE_PENALTY_THRESHOLD:
            overage = self.age - config.AGE_PENALTY_THRESHOLD
            age_factor = 1.0 + overage * 0.02  # +2% per year over 60

        # Force bonus: stronger = faster (linear from 1.0 at force=0 to 0.6 at force=100)
        force_multiplier = 1.0 - (self.force / 100.0) * 0.4

        delay = config.TICK_SPEED * age_factor * force_multiplier
        return max(0.04, delay)

    # ------------------------------------------------------------------
    # Utility distance
    # ------------------------------------------------------------------

    def distance_to(self, other_pos: Tuple[int, int]) -> float:
        """
        Calculates the Euclidean distance to another position.

        Args:
            other_pos: Destination position (x, y).

        Returns:
            float: Distance in cells.
        """
        dx = self.pos[0] - other_pos[0]
        dy = self.pos[1] - other_pos[1]
        return math.sqrt(dx * dx + dy * dy)

    # ------------------------------------------------------------------
    # Abstract methods that subclasses must implement
    # ------------------------------------------------------------------

    def clone(self, **overrides) -> "Agent":
        """
        Prototype pattern: creates a shallow copy of the agent with overrides.

        Builds a new agent of the same (or overridden) type, copying core
        attributes and applying any keyword overrides.  The clone is NOT
        started — callers must call .start() after placement.

        This is used by Engine.convert_infected() so the expensive object
        construction happens OUTSIDE the world lock, and only the brief
        grid-swap (remove old + place new) needs the lock.

        Args:
            **overrides: Attribute overrides (pos, force, age, etc.).

        Returns:
            A new Agent instance (not yet started or placed).

        References:
            https://refactoring.guru/design-patterns/prototype
        """
        cls = overrides.pop("cls", self.__class__)
        pos = overrides.pop("pos", self.pos)
        force = overrides.pop("force", self.force)
        age = overrides.pop("age", self.age)
        return cls(pos=pos, world=self.world, force=force, age=age, **overrides)

    @abstractmethod
    def update(self) -> None:
        """
        Per-tick update logic.

        Each subclass defines its behavior here: movement,
        threat detection, combat, etc.
        """
        ...

    @abstractmethod
    def get_color(self) -> str:
        """
        Returns the representation color for the UI.

        Returns:
            str: Tkinter-compatible color (e.g. "red", "#ff0000").
        """
        ...

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.agent_id}, "
            f"pos={self.pos}, state={self.state}, force={self.force})"
        )

