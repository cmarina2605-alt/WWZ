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
        # Survival attributes
        self.food: float = float(config.INITIAL_FOOD)
        self.water: float = float(config.INITIAL_WATER)
        self._original_force: int = self.force  # Store base force before starvation
        # Refuge (military base shelter) tracking
        self.in_refuge: bool = False
        self.refuge_ticks: int = 0          # How many ticks spent in refuge
        self.refuge_cooldown: int = 0       # Cooldown before re-entry

    # ------------------------------------------------------------------
    # Main logic
    # ------------------------------------------------------------------

    def update(self, _survival_done: bool = False) -> None:
        """
        Per-tick update logic for humans.

        1. Updates refuge state (cooldown, eviction).
        2. If sheltered in refuge, stays put (safe from zombies).
        3. Detects nearby zombies and updates fear.
        4. Calculates the next position (via movement).
        5. Checks for zombie encounters at the new position.
        6. Updates state based on context.

        Args:
            _survival_done: Internal flag set by subclasses (e.g. Scientist)
                that already called _update_survival() to avoid double depletion.
        """
        from simulation import movement, combat

        if not self.is_alive():
            return

        # --- Refuge cooldown ---
        if self.refuge_cooldown > 0:
            self.refuge_cooldown -= 1

        # --- Refuge logic ---
        dist_to_base = self.distance_to(config.MILITARY_BASE_POS)
        if self.in_refuge:
            self.refuge_ticks += 1
            if self.refuge_ticks >= config.REFUGE_MAX_TICKS:
                # Evicted! Time's up — make room for others
                self.in_refuge = False
                self.refuge_cooldown = config.REFUGE_COOLDOWN_TICKS
                self.refuge_ticks = 0
                self.world.push_event(
                    "refuge",
                    f"🚪 Human {self.agent_id} evicted from Fort Bragg refuge (time limit)",
                )
            else:
                # Safe inside — reduce fear, resupply, skip movement
                self.fear = max(0, self.fear - 10)
                if self.state == "running":
                    self.set_state("calm")
                # Regenerate food/water while sheltered
                self.food = min(config.INITIAL_FOOD, self.food + config.REFUGE_FOOD_REGEN)
                self.water = min(config.INITIAL_WATER, self.water + config.REFUGE_WATER_REGEN)
                if self.force < self._original_force:
                    self.force = min(self._original_force, self.force + 1)
                return
        elif (
            dist_to_base <= config.MILITARY_BASE_RADIUS
            and self.refuge_cooldown == 0
            and self.fear > 30
        ):
            # Enter refuge if near the base, scared, and not on cooldown
            self.in_refuge = True
            self.refuge_ticks = 0
            self.fear = max(0, self.fear - 30)
            self.world.push_event(
                "refuge",
                f"🏕 Human {self.agent_id} takes shelter at Fort Bragg",
            )
            return

        # --- Survival: food & water ---
        if not _survival_done:
            self._update_survival()
            if not self.is_alive():
                return

        # Single scan for nearby agents — reused for fear, movement, and combat
        # This replaces 3-4 separate get_agents_in_radius calls per tick
        nearby = self.world.get_agents_in_radius(self.pos, config.VISION_HUMAN)
        zombies_nearby = [a for a in nearby if a.__class__.__name__ == "Zombie"]

        # Update fear
        self._update_fear(len(zombies_nearby))

        # Panic propagation (uses already-fetched nearby list)
        if self.state not in ("fighting", "dead", "infected"):
            running_count = sum(1 for a in nearby if a.state == "running")
            if running_count >= 4 and self.state == "calm":
                self.set_state("running")
                self.fear = min(100, self.fear + 20)

        # Calculate next position (pass cached nearby to avoid re-scanning)
        next_pos = movement.calculate_next_pos(self, self.world, nearby)

        # Check for zombie at the destination — use distance check instead
        # of a second get_agents_in_radius call
        zombie_at_dest = None
        for z in zombies_nearby:
            dx = z.pos[0] - next_pos[0]
            dy = z.pos[1] - next_pos[1]
            if dx * dx + dy * dy <= 2:  # within ~1.4 cells
                zombie_at_dest = z
                break

        if zombie_at_dest:
            combat.resolve_encounter(self, zombie_at_dest, self.world)
        else:
            # Move the agent
            self.world.move_agent(self, next_pos)

    def _update_survival(self) -> None:
        """
        Updates food and water levels each tick.

        When resources hit zero, the agent gradually loses force.
        If force drops below DEATH_FORCE_THRESHOLD from starvation/
        dehydration, the agent dies.

        While in refuge, food and water regenerate instead.
        """
        # Consume resources
        self.food = max(0.0, self.food - config.FOOD_DECAY_PER_TICK)
        self.water = max(0.0, self.water - config.WATER_DECAY_PER_TICK)

        # Starvation penalty
        force_penalty = 0.0
        if self.food <= config.STARVATION_THRESHOLD:
            force_penalty += config.FORCE_LOSS_NO_FOOD
        if self.water <= config.DEHYDRATION_THRESHOLD:
            force_penalty += config.FORCE_LOSS_NO_WATER

        if force_penalty > 0:
            self.force = max(0, int(self.force - force_penalty))
            # Recalculate speed (weaker = slower)
            self.move_delay = self._calculate_move_delay()

            if self.force <= config.DEATH_FORCE_THRESHOLD:
                cause = []
                if self.food <= 0:
                    cause.append("starvation")
                if self.water <= 0:
                    cause.append("dehydration")
                self.die()
                self.world.push_event(
                    "death",
                    f"☠️ Human {self.agent_id} died of {' and '.join(cause)}",
                )
                # Observer pattern: notify EventBus
                if self.world.event_bus:
                    self.world.event_bus.publish("human_died", {
                        "human_id": self.agent_id,
                        "cause": " and ".join(cause),
                    })

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

        # Survival: food & water still deplete even for scientists
        self._update_survival()
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
            super().update(_survival_done=True)
        elif self.in_lab and not antidote_ready.is_set():
            self._work_on_antidote()
            self._update_fear(0)  # The scientist calms down while working
        elif not self.in_lab:
            # Move toward the laboratory
            self._update_fear(0)
            next_pos = movement.move_towards(self.pos, config.LAB_POS, self.world)
            self.world.move_agent(self, next_pos)
        else:
            super().update(_survival_done=True)

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
            # Observer pattern: notify EventBus for instant win detection
            if self.world.event_bus:
                self.world.event_bus.publish("antidote_complete", {"scientist_id": self.agent_id})

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

        Military units resupply ammunition when near the military base.
        """
        from simulation import movement, combat

        if not self.is_alive():
            return

        # Resupply ammo at military base
        dist_to_base = self.distance_to(config.MILITARY_BASE_POS)
        if dist_to_base <= config.MILITARY_BASE_RADIUS and self.ammo < 5:
            self.ammo += config.MILITARY_AMMO_RESUPPLY
            self.world.push_event(
                "resupply",
                f"🔄 Military {self.agent_id} resupplied at Fort Bragg (+{config.MILITARY_AMMO_RESUPPLY} ammo)",
            )

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
            # If a president exists and no immediate threat, move to protect them
            president = self._find_president()
            if president and self.distance_to(president.pos) > 3:
                # Move toward the president to form a protective escort
                next_pos = movement.move_towards(self.pos, president.pos, self.world)
                self.world.move_agent(self, next_pos)
            else:
                # Standard behavior (flee or patrol near president)
                super().update()

    def _find_president(self):
        """
        Searches for the living president among nearby agents.

        Returns:
            The president Politician if found within extended vision, or None.
        """
        nearby = self.world.get_agents_in_radius(self.pos, config.VISION_ZOMBIE)  # Extended range
        for a in nearby:
            if isinstance(a, Politician) and getattr(a, "is_president", False) and a.is_alive():
                return a
        return None

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
        self.is_president: bool = False  # Set to True when chosen as president
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
        if self.is_president:
            return config.COLOR_PRESIDENT
        return config.COLOR_POLITICIAN
