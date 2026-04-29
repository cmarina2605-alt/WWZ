"""
commands.py — Command pattern for UI actions and combat outcomes.

Design Pattern: COMMAND
    Encapsulates actions as objects, decoupling the invoker (UI buttons,
    combat system) from the receiver (Engine, agents). Each command stores
    enough state to describe what happened, enabling:

    - Undo/redo potential (for UI commands like pause/resume).
    - Replay: CommandHistory records every combat outcome so it can be
      replayed for debugging, analysis or the post-game summary.
    - Loose coupling: the ControlPanel doesn't call engine methods
      directly — it creates command objects and executes them.

Architecture:
    Command (ABC)
        ├── StartCommand        — starts the simulation
        ├── PauseCommand        — toggles pause / resume
        ├── ResetCommand        — resets the simulation
        ├── EscapeCommand       — human escapes a zombie
        ├── InfectCommand       — human gets infected
        ├── KillHumanCommand    — human dies in combat
        └── KillZombieCommand   — zombie is eliminated

    CommandHistory
        - Stores a chronological list of executed commands.

References:
    https://refactoring.guru/design-patterns/command
"""

import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.engine import Engine
    from agents.human import Human
    from agents.zombie import Zombie
    from simulation.world import World


# ═══════════════════════════════════════════════════════════════════════
# Abstract base
# ═══════════════════════════════════════════════════════════════════════

class Command(ABC):
    """
    Abstract base for all commands.

    Every command knows how to execute() itself. Combat commands also
    carry a description for logging and a tick timestamp.

    Attributes:
        description (str): Human-readable summary of the action.
        tick (int): Simulation tick when the command was created.
    """

    def __init__(self, description: str = "", tick: int = 0) -> None:
        self.description: str = description
        self.tick: int = tick

    @abstractmethod
    def execute(self) -> None:
        """Performs the encapsulated action."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(tick={self.tick}, desc={self.description!r})"


# ═══════════════════════════════════════════════════════════════════════
# UI commands  (invoker: ControlPanel → receiver: Engine)
# ═══════════════════════════════════════════════════════════════════════

class StartCommand(Command):
    """
    Starts the simulation.

    Encapsulates engine.start_simulation() so the UI button handler
    doesn't need a direct reference to Engine internals.
    """

    def __init__(self, engine: "Engine") -> None:
        super().__init__(description="Start simulation")
        self.engine = engine

    def execute(self) -> None:
        if not self.engine.running:
            self.engine.start_simulation()


class PauseCommand(Command):
    """
    Toggles pause/resume.

    Stores the previous paused state so the action is self-describing
    in the CommandHistory.
    """

    def __init__(self, engine: "Engine") -> None:
        super().__init__(description="Toggle pause")
        self.engine = engine
        self._was_paused: Optional[bool] = None

    def execute(self) -> None:
        self._was_paused = self.engine.paused
        self.engine.pause()
        action = "Resumed" if self._was_paused else "Paused"
        self.description = f"{action} simulation"


class ResetCommand(Command):
    """
    Resets the simulation to its initial state.

    After execution, the engine is ready for a new StartCommand.
    """

    def __init__(self, engine: "Engine") -> None:
        super().__init__(description="Reset simulation")
        self.engine = engine

    def execute(self) -> None:
        self.engine.reset()


# ═══════════════════════════════════════════════════════════════════════
# Combat commands  (invoker: combat.py → receiver: agents)
# ═══════════════════════════════════════════════════════════════════════

class EscapeCommand(Command):
    """
    Records and applies a human-escape outcome.

    Sets the human to "running" state.
    """

    def __init__(
        self,
        human: "Human",
        zombie: "Zombie",
        world: "World",
        tick: int = 0,
    ) -> None:
        super().__init__(
            description=f"Human {human.agent_id} escaped Zombie {zombie.agent_id}",
            tick=tick,
        )
        self.human = human
        self.zombie = zombie
        self.world = world

    def execute(self) -> None:
        self.human.set_state("running")
        self.world.push_event(
            "escape",
            f"🏃 {self.description}",
        )


class InfectCommand(Command):
    """
    Records and applies a human-infected outcome.

    Marks the human as infected; the Engine's InfectionMonitor
    handles the actual conversion after the incubation period.
    """

    def __init__(
        self,
        human: "Human",
        zombie: "Zombie",
        world: "World",
        tick: int = 0,
    ) -> None:
        super().__init__(
            description=f"Human {human.agent_id} infected by Zombie {zombie.agent_id}",
            tick=tick,
        )
        self.human = human
        self.zombie = zombie
        self.world = world

    def execute(self) -> None:
        self.human.infect()
        self.world.push_event("infection", f"🧟 {self.description}")
        # Observer pattern: publish to EventBus
        if self.world.event_bus:
            self.world.event_bus.publish("human_infected", {
                "human_id": self.human.agent_id,
                "zombie_id": self.zombie.agent_id,
            })


class KillHumanCommand(Command):
    """
    Records and applies a human-death outcome.

    Kills the human immediately (no infection).
    """

    def __init__(
        self,
        human: "Human",
        zombie: "Zombie",
        world: "World",
        tick: int = 0,
    ) -> None:
        super().__init__(
            description=f"Human {human.agent_id} killed by Zombie {zombie.agent_id}",
            tick=tick,
        )
        self.human = human
        self.zombie = zombie
        self.world = world

    def execute(self) -> None:
        self.human.die()
        self.world.push_event("death", f"💀 {self.description}")
        if self.world.event_bus:
            self.world.event_bus.publish("human_died", {
                "human_id": self.human.agent_id,
                "zombie_id": self.zombie.agent_id,
            })


class KillZombieCommand(Command):
    """
    Records and applies a zombie-death outcome.

    Eliminates the zombie from the simulation.
    """

    def __init__(
        self,
        human: "Human",
        zombie: "Zombie",
        world: "World",
        tick: int = 0,
    ) -> None:
        super().__init__(
            description=f"Zombie {zombie.agent_id} eliminated by Human {human.agent_id}",
            tick=tick,
        )
        self.human = human
        self.zombie = zombie
        self.world = world

    def execute(self) -> None:
        # Consume ammo on the kill shot (moved from _calculate_probabilities)
        if hasattr(self.human, "use_ammo"):
            self.human.use_ammo()
        self.zombie.die()
        self.world.push_event("zombie_death", f"🔫 {self.description}")
        if self.world.event_bus:
            self.world.event_bus.publish("zombie_killed", {
                "zombie_id": self.zombie.agent_id,
                "human_id": self.human.agent_id,
            })


# ═══════════════════════════════════════════════════════════════════════
# Command History — stores executed commands for replay / analytics
# ═══════════════════════════════════════════════════════════════════════

class CommandHistory:
    """
    Thread-safe log of all executed commands.

    Used primarily for combat commands so the post-game summary
    or a replay system can iterate over every encounter that happened.

    Attributes:
        _history (List[Command]): Chronological list of commands.
        _lock (threading.Lock): Protects concurrent appends.
    """

    def __init__(self) -> None:
        self._history: List[Command] = []
        self._lock: threading.Lock = threading.Lock()

    def execute(self, command: Command) -> None:
        """
        Executes a command and records it in the history.

        Args:
            command: The command to execute and log.
        """
        command.execute()
        with self._lock:
            self._history.append(command)

    def clear(self) -> None:
        """Clears all history (used on simulation reset)."""
        with self._lock:
            self._history.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._history)

    def __repr__(self) -> str:
        return f"CommandHistory(commands={len(self)})"
