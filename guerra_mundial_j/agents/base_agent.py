"""
base_agent.py — Abstract base class for all simulation agents.

Defines the common lifecycle of any world entity (human or zombie):
starting the thread, executing update() every move_delay seconds and stopping
when game_over is set or the agent dies.

Responsibilities of this class:
    - Thread-safe unique ID generation for each agent.
    - run() loop: calls update(), sleeps move_delay and repeats.
    - move_delay calculation based on age and force:
        more age → slower; more force → faster.
    - Valid states: calm | running | fighting | infected | dead.
    - Global signals (threading.Event) accessible from any module:
        · game_over      — stops all agents.
        · antidote_ready — scientists have completed the antidote.
        · national_alert — the politician has issued an emergency alert.

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

if TYPE_CHECKING:
    from simulation.world import World

# Global signals shared by the entire simulation
game_over: threading.Event = threading.Event()
antidote_ready: threading.Event = threading.Event()
national_alert: threading.Event = threading.Event()

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
            if self.state == "dead":
                break
            try:
                self.update()
            except Exception as exc:
                # Prevent an error in one agent from crashing the main thread
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

        Args:
            new_state: New state. Must belong to VALID_STATES.

        Raises:
            ValueError: If new_state is not a valid state.
        """
        if new_state not in self.VALID_STATES:
            raise ValueError(f"Invalid state: '{new_state}'. Valid states: {self.VALID_STATES}")
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

        Returns:
            float: Wait seconds between ticks.
        """
        # Age penalty
        age_factor = 1.0
        if self.age > config.AGE_PENALTY_THRESHOLD:
            age_factor = 1.0 + (self.age - config.AGE_PENALTY_THRESHOLD) * 0.02

        # Force bonus
        force_factor = 1.0 - (self.force / 200.0)  # up to 50% faster

        delay = config.TICK_SPEED * age_factor * (0.5 + force_factor)
        return max(0.05, delay)

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

