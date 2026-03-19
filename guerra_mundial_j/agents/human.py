"""
human.py — Human agent classes for the simulation.

Implements the hierarchy of humans that populate the grid:

    Human (Agent)   — base: has fear and empathy.
    ├── Normal       — ordinary citizen with no special skills; flees from zombies.
    ├── Scientist    — actively navigates toward the laboratory (LAB_POS) to
    │                  work on the antidote; flees if zombies are detected nearby.
    ├── Military     — if force > FORCE_FLEE_THRESHOLD, chases zombies instead
    │                  of fleeing; uses ammo to increase kill probability.
    └── Politician   — emits national alerts (national_alert) when seeing zombies,
                       which speeds up the military response.

Key mechanics:
    - Fear: increases when zombies are seen, decreases over time.
      High fear activates the "running" state and can penalize attributes.
    - Social panic (panic_spread): if ≥4 neighbors are running, the agent
      enters panic even without directly seeing zombies.
    - Infection: Human.infect() marks the state as "infected"; the actual
      conversion to Zombie is managed by the Engine's InfectionMonitor.
    - Antidote: when a Scientist accumulates enough ticks in the lab,
      it activates antidote_ready and pushes an event to the EventLog.
"""

import random
import threading
from typing import Tuple, Optional, TYPE_CHECKING

import config
from agents.base_agent import Agent, antidote_ready, national_alert

if TYPE_CHECKING:
    from simulation.world import World


class Human(Agent):
    """
    Base human agent.

    Extends Agent by adding empathy and fear, which modulate
    flee, grouping and combat decisions.

    Attributes:
        empathy (int): Tendency to help others (0-100).
        fear (int): Current panic level (0-100); increases when zombies are seen.
        role (str): Human role (normal/scientist/military/politician).
    """

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        force: int = 50,
        age: int = 30,
        empathy: int = 50,
        fear: int = 10,
    ) -> None:
        """
        Initializes a human with empathy and fear.

        Args:
            pos: Initial position (x, y).
            world: Reference to the shared world.
            force: Physical force (0-100).
            age: Agent age.
            empathy: Empathy level (0-100).
            fear: Initial fear (0-100).
        """
        super().__init__(pos=pos, world=world, force=force, age=age)
        self.empathy: int = max(0, min(100, empathy))
        self.fear: int = max(0, min(100, fear))
        self.role: str = "normal"

    # ------------------------------------------------------------------
    # Main logic
    # ------------------------------------------------------------------

    def update(self) -> None:
        """
        Per-tick update logic for humans.

        1. Detects nearby zombies and updates fear.
        2. Calculates the next position (via movement).
        3. Checks for zombie encounters at the new position.
        4. Updates state based on context.
        """
        from simulation import movement, combat

        if not self.is_alive():
            return

        # Detect zombies within vision range
        nearby = self.world.get_agents_in_radius(self.pos, config.VISION_HUMAN)
        zombies_nearby = [a for a in nearby if a.__class__.__name__ == "Zombie"]

        # Update fear
        self._update_fear(len(zombies_nearby))

        # Calculate next position
        next_pos = movement.calculate_next_pos(self, self.world)

        # Check if there is a zombie at the destination cell or adjacent
        agents_at_dest = self.world.get_agents_in_radius(next_pos, 1)
        zombies_at_dest = [a for a in agents_at_dest if a.__class__.__name__ == "Zombie"]

        if zombies_at_dest:
            zombie = zombies_at_dest[0]
            combat.resolve_encounter(self, zombie, self.world)
        else:
            # Move the agent
            self.world.move_agent(self, next_pos)

        # Panic propagation
        movement.panic_spread(self, self.world)

    def _update_fear(self, zombie_count: int) -> None:
        """
        Updates the fear level based on the number of visible zombies.

        Args:
            zombie_count: Number of zombies detected within vision range.
        """
        if zombie_count > 0:
            self.fear = min(100, self.fear + zombie_count * 10)
            self.set_state("running")
        else:
            self.fear = max(0, self.fear - 5)
            if self.fear < 20 and self.state == "running":
                self.set_state("calm")

    def get_color(self) -> str:
        """Returns the color based on the human's role."""
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_NORMAL

    def infect(self) -> None:
        """
        Marks the human as infected.

        This begins the conversion process to zombie, managed
        by the simulation engine.
        """
        self.set_state("infected")

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.agent_id}, role={self.role}, "
            f"pos={self.pos}, fear={self.fear}, state={self.state})"
        )


# ---------------------------------------------------------------------------
# Specialized subclasses
# ---------------------------------------------------------------------------

class Normal(Human):
    """
    Ordinary human with no special skills.

    Standard behavior: flees from zombies and seeks shelter.
    """

    def __init__(self, pos: Tuple[int, int], world: "World", **kwargs) -> None:
        super().__init__(pos=pos, world=world, **kwargs)
        self.role = "normal"

    def get_color(self) -> str:
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_NORMAL


class Scientist(Human):
    """
    Scientist who can contribute to the antidote.

    Attributes:
        intelligence (int): Intelligence level (0-100); reduces the time
            needed to complete the antidote.
        antidote_progress (int): Ticks accumulated working on the antidote.
        in_lab (bool): Whether currently at the science base.
    """

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        intelligence: int = 70,
        **kwargs,
    ) -> None:
        """
        Initializes a Scientist with additional intelligence.

        Args:
            intelligence: Intelligence level (0-100).
        """
        super().__init__(pos=pos, world=world, **kwargs)
        self.role = "scientist"
        self.intelligence: int = max(0, min(100, intelligence))
        self.antidote_progress: int = 0
        self.in_lab: bool = False

    def update(self) -> None:
        """
        Scientist update logic.

        Priority:
        1. If zombies are nearby → flee (standard human behavior).
        2. If in the lab → work on the antidote.
        3. If not in the lab → move toward it.
        """
        from simulation import movement

        if not self.is_alive():
            return

        # Detect if we are near the laboratory
        dist_to_lab = self.distance_to(config.LAB_POS)
        if dist_to_lab <= config.LAB_RADIUS:
            self.in_lab = True

        # If zombies are nearby, fleeing takes priority over the laboratory
        nearby = self.world.get_agents_in_radius(self.pos, config.VISION_HUMAN)
        zombies_nearby = [a for a in nearby if a.__class__.__name__ == "Zombie"]

        if zombies_nearby:
            self.in_lab = False  # Leave the lab if there is danger
            super().update()
        elif self.in_lab and not antidote_ready.is_set():
            self._work_on_antidote()
            self._update_fear(0)  # The scientist calms down while working
        elif not self.in_lab:
            # Move toward the laboratory
            self._update_fear(0)
            next_pos = movement.move_towards(self.pos, config.LAB_POS, self.world)
            self.world.move_agent(self, next_pos)
        else:
            super().update()

    def _work_on_antidote(self) -> None:
        """
        Advances antidote research.

        Progress increases based on the scientist's intelligence (1–4 per tick).
        Intelligence no longer reduces the total ticks needed — only the rate.
        When complete, activates the global antidote_ready event.
        """
        progress_rate = 1 + int(self.intelligence / 33)   # 1–4 per tick
        self.antidote_progress += progress_rate

        if self.antidote_progress >= config.ANTIDOTE_TICKS:
            antidote_ready.set()
            national_alert.set()
            self.world.push_event(
                "antidote",
                f"💉 ANTIDOTE COMPLETED! Scientist #{self.agent_id} has found the cure",
            )

    def get_color(self) -> str:
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_SCIENTIST


class Military(Human):
    """
    Military with increased strength and aggressive combat behavior.

    Unlike civilians, does not flee if their strength exceeds
    FORCE_FLEE_THRESHOLD; instead enters the "fighting" state.

    Attributes:
        ammo (int): Available ammunition (affects probability of killing a zombie).
    """

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        ammo: int = 10,
        **kwargs,
    ) -> None:
        """
        Initializes a Military with a strength bonus and ammunition.

        Args:
            ammo: Initial ammunition.
        """
        # Apply strength bonus
        force = kwargs.pop("force", 50)
        force = min(100, force + config.FORCE_MILITARY_BONUS)
        super().__init__(pos=pos, world=world, force=force, **kwargs)
        self.role = "military"
        self.ammo: int = ammo

    def update(self) -> None:
        """
        Military update logic.

        If strength exceeds the threshold, actively seeks zombies to
        fight instead of fleeing.

        With "military_first" strategy: expanded vision radius (VISION_ZOMBIE)
        and reduced strength threshold to 30, so almost all military units fight.
        """
        from simulation import movement, combat

        if not self.is_alive():
            return

        strategy = getattr(self.world, "strategy", "none")
        if strategy == "military_first":
            vision = config.VISION_ZOMBIE
            force_threshold = 30
        else:
            vision = config.VISION_HUMAN
            force_threshold = config.FORCE_FLEE_THRESHOLD

        nearby = self.world.get_agents_in_radius(self.pos, vision)
        zombies_nearby = [a for a in nearby if a.__class__.__name__ == "Zombie"]

        if zombies_nearby and self.force > force_threshold:
            # Aggressive behavior: approach the closest zombie
            self.set_state("fighting")
            closest = min(zombies_nearby, key=lambda z: self.distance_to(z.pos))
            # Move toward the zombie
            next_pos = movement.move_towards(self.pos, closest.pos, self.world)
            agents_at = self.world.get_agents_in_radius(next_pos, 0)
            if any(a.__class__.__name__ == "Zombie" for a in agents_at):
                combat.resolve_encounter(self, closest, self.world)
            else:
                self.world.move_agent(self, next_pos)
        else:
            # Standard behavior (flee)
            super().update()

    def use_ammo(self) -> bool:
        """
        Consumes one unit of ammunition.

        Returns:
            bool: True if ammunition was available and consumed.
        """
        if self.ammo > 0:
            self.ammo -= 1
            return True
        return False

    def get_color(self) -> str:
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_MILITARY


class Politician(Human):
    """
    Politician with high empathy who can issue national alerts.

    Has the ability to activate the national_alert event when
    a critical situation is detected, which accelerates the military response.

    Attributes:
        influence (int): Influence level (0-100); affects the probability
            that the alert is effective.
        alert_cooldown (int): Ticks remaining until another alert can be issued.
    """

    ALERT_COOLDOWN_TICKS: int = 50

    # Available ideologies and the strategy each one proposes
    IDEOLOGY_STRATEGIES: dict = {
        "hawk":      "military_first",  # The Hawk: full military response
        "populist":  "flee",            # The Populist: evacuate the people first
        "socialist": "group",           # The Socialist: strength in unity
        "chaotic":   "random",          # The Indecisive: the government can't agree
    }

    IDEOLOGY_NAMES: dict = {
        "hawk":      "The Hawk",
        "populist":  "The Populist",
        "socialist": "The Socialist",
        "chaotic":   "The Indecisive",
    }

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        influence: int = 80,
        ideology: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Initializes a Politician with high empathy, influence, and ideology.

        Args:
            influence: Political influence level (0-100). Determines who
                wins the debate when multiple politicians are alive.
            ideology: One of "hawk", "populist", "socialist", "chaotic".
                If None, assigned randomly.
        """
        empathy = kwargs.pop("empathy", 80)
        super().__init__(pos=pos, world=world, empathy=empathy, **kwargs)
        self.role = "politician"
        self.influence: int = max(0, min(100, influence))
        self.ideology: str = ideology if ideology in self.IDEOLOGY_STRATEGIES else random.choice(list(self.IDEOLOGY_STRATEGIES))
        self.alert_cooldown: int = 0
        self._alert_messages: list[str] = [
            "📨 Message reaches the White House",
            "📨 National state of emergency declared",
            "📨 Protocol Z activated",
        ]

    def update(self) -> None:
        """
        Politician update logic.

        Tries to issue national alerts when zombies are detected and
        follows standard human behavior.
        """
        if not self.is_alive():
            return

        if self.alert_cooldown > 0:
            self.alert_cooldown -= 1

        nearby = self.world.get_agents_in_radius(self.pos, config.VISION_HUMAN)
        zombies_nearby = [a for a in nearby if a.__class__.__name__ == "Zombie"]

        if zombies_nearby and self.alert_cooldown == 0:
            self._emit_alert()

        super().update()

    def _emit_alert(self) -> None:
        """
        Issues a national alert if conditions are met.

        Success probability depends on the influence level.
        """
        if random.random() < self.influence / 100.0:
            national_alert.set()
            self.alert_cooldown = self.ALERT_COOLDOWN_TICKS
            msg = random.choice(self._alert_messages)
            self.world.push_event("alert", msg)

    def get_color(self) -> str:
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_POLITICIAN
