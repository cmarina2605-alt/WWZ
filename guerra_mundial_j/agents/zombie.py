"""
zombie.py — Zombie class for the Guerra Mundial J simulation.

In the simulation universe, zombies are copies of Professor José:
the result of the failed experiment that unleashed the apocalypse.

Per-tick behavior:
    1. Hunger increases each tick; the hungrier, the faster.
    2. Searches for the nearest living human within VISION_ZOMBIE cells.
    3. If found, chases it (move_towards) and attacks on contact
       (distance ≤ 1.5): delegates to combat.resolve_encounter().
    4. If no human is visible, performs a random walk.

Targeting system:
    - Stores target_id to maintain the target between ticks.
    - If the target disappears (dead, fled, or out of range), retargets.

The conversion of infected humans does NOT happen here; it is managed by the
Engine's InfectionMonitor to avoid race conditions when creating new threads.
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
    Zombie agent that chases and attacks humans.

    Attributes:
        target_id (Optional[int]): ID of the current target human.
        infection_count (int): Number of humans infected by this zombie.
        hunger (int): Hunger level (0-100); increases over time,
            decreases when attacking. Affects movement speed.
    """

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        force: int = 60,
        age: int = 25,
    ) -> None:
        """
        Initializes a zombie.

        Args:
            pos: Initial position (x, y).
            world: Reference to the shared world.
            force: Initial zombie strength (0-100).
            age: Apparent age of the zombie.
        """
        self.hunger: int = 50  # Must be initialized BEFORE super() (used in _calculate_move_delay)
        super().__init__(pos=pos, world=world, force=force, age=age)
        self.target_id: Optional[int] = None
        self.infection_count: int = 0
        self.set_state("calm")

    # ------------------------------------------------------------------
    # Main logic
    # ------------------------------------------------------------------

    def update(self) -> None:
        """
        Per-tick update logic for the zombie.

        1. Increases hunger slightly each tick.
        2. Searches for the nearest human within vision range.
        3. If found, chases and attacks on contact.
        4. If no target visible, performs random walk.
        """
        from simulation import movement, combat

        if not self.is_alive():
            return

        # Gradually increase hunger
        self.hunger = min(100, self.hunger + 1)

        # Recalculate speed based on hunger
        self.move_delay = self._calculate_move_delay()

        # Find target
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
        Searches for the nearest living human within vision range.

        Returns:
            The nearest human agent, or None if none is visible.
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
        Pursues the target and attacks if in contact.

        Args:
            target: Target human.
            combat: Combat module.
            movement: Movement module.
        """
        dist = self.distance_to(target.pos)

        if dist <= 1.5:
            # In contact: resolve encounter
            self.set_state("fighting")
            combat.resolve_encounter(target, self, self.world)
            self.hunger = max(0, self.hunger - 30)
            self.infection_count += 1
        else:
            # Chase
            self.set_state("calm")
            next_pos = movement.move_towards(self.pos, target.pos, self.world)
            self.world.move_agent(self, next_pos)

    def _calculate_move_delay(self) -> float:
        """
        Calculates the movement delay.

        Hungrier zombies move slightly faster.

        Returns:
            float: Wait seconds between ticks.
        """
        base = super()._calculate_move_delay()
        # Hunger reduces delay (up to 20% faster)
        hunger_factor = 1.0 - (self.hunger / 500.0)
        return max(0.05, base * hunger_factor)

    # ------------------------------------------------------------------
    # Visual representation
    # ------------------------------------------------------------------

    def get_color(self) -> str:
        """Returns the zombie's color for the UI."""
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_ZOMBIE

    def __repr__(self) -> str:
        return (
            f"Zombie(id={self.agent_id}, pos={self.pos}, "
            f"target={self.target_id}, infections={self.infection_count})"
        )
