"""
combat.py — Resolution of encounters between humans and zombies.

When a human and a zombie meet on the same or adjacent cell,
this module calculates the probabilistic outcome of the confrontation.

Possible outcomes (Outcome):
    "escape"         — the human manages to flee (set_state "running").
    "human_infected" — the human is infected (human.infect()); the Engine
                       will turn it into a zombie after the incubation period.
    "human_dies"     — the human dies directly (human.die()).
    "zombie_dies"    — the zombie is eliminated (zombie.die()).

Factors influencing the probabilities:
    - force_ratio (human / zombie): higher relative force → easier to escape.
    - age: if the human exceeds AGE_PENALTY_THRESHOLD, p_infect increases.
    - role: Military with ammo adds +0.3 to p_zombie_dies; non-military
      have reduced p_zombie_dies.
    - Base randomness: the outcome always has a random component so
      the simulation remains unpredictable.

All effects (dying, infecting, fleeing) are applied directly to
the agents, and a descriptive event is pushed to the world's EventLog.
"""

import random
from typing import Literal, Optional, TYPE_CHECKING

import config
from commands import (
    EscapeCommand,
    InfectCommand,
    KillHumanCommand,
    KillZombieCommand,
    CommandHistory,
)

if TYPE_CHECKING:
    from agents.human import Human
    from agents.zombie import Zombie
    from simulation.world import World

# Type for the result of an encounter
Outcome = Literal["escape", "human_dies", "human_infected", "zombie_dies"]


def resolve_encounter(
    human: "Human",
    zombie: "Zombie",
    world: "World",
) -> Outcome:
    """
    Resolves an encounter between a human and a zombie.

    The probability of each outcome depends on:
    - force of the human and the zombie.
    - age of the human (penalty if elderly).
    - role of the human (Military has bonus).
    - Base randomness.

    Side effects are applied directly to the agents
    under world.lock when necessary.

    Args:
        human: The human agent involved.
        zombie: The zombie agent involved.
        world: The shared world (for conversions).

    Returns:
        Outcome: Result of the encounter.
    """
    # Calculate base probabilities
    p_escape, p_infect, p_human_dies, p_zombie_dies = _calculate_probabilities(
        human, zombie
    )

    # Normalize (must sum to 1)
    total = p_escape + p_infect + p_human_dies + p_zombie_dies
    if total <= 0:
        return "escape"

    p_escape /= total
    p_infect /= total
    p_human_dies /= total
    p_zombie_dies /= total

    # Select outcome
    roll = random.random()
    if roll < p_zombie_dies:
        outcome: Outcome = "zombie_dies"
    elif roll < p_zombie_dies + p_escape:
        outcome = "escape"
    elif roll < p_zombie_dies + p_escape + p_infect:
        outcome = "human_infected"
    else:
        outcome = "human_dies"

    # Apply outcome effects
    _apply_outcome(outcome, human, zombie, world)
    return outcome


def _calculate_probabilities(
    human: "Human",
    zombie: "Zombie",
) -> tuple[float, float, float, float]:
    """
    Calculates the raw probabilities of each outcome.

    Args:
        human: Human agent.
        zombie: Zombie agent.

    Returns:
        Tuple (p_escape, p_infect, p_human_dies, p_zombie_dies).
    """
    from agents.human import Military

    # Relative force
    force_ratio = human.force / max(1, zombie.force)

    # Base escape probability (more force → easier to escape)
    # Stronger humans escape much more easily; capped at 0.75
    p_escape = config.P_ESCAPE * (0.5 + force_ratio * 0.8)
    p_escape = min(0.75, max(0.08, p_escape))

    # Infection probability
    p_infect = config.P_INFECT
    if human.age > config.AGE_PENALTY_THRESHOLD:
        p_infect += 0.08  # More vulnerable if elderly (was 0.10)
    # Slightly reduce infection chance for strong humans
    p_infect *= max(0.6, 1.0 - force_ratio * 0.2)

    # Probability that the human dies directly
    # Lower base (0.15 instead of 0.3) — infection is the main threat, not instant death
    p_human_dies = max(0.0, (0.15 - force_ratio * 0.1) * (1 - config.P_INFECT))

    # Probability that the zombie dies
    # Note: ammo is consumed in _apply_outcome, not here — this is a pure calculation
    p_zombie_dies = config.P_KILL_ZOMBIE
    if isinstance(human, Military) and human.ammo > 0:
        p_zombie_dies += 0.25   # Military with ammo is a real threat
    elif isinstance(human, Military):
        # Military without ammo still fights better than civilians
        p_zombie_dies += 0.05
    else:
        # Civilians can barely kill zombies
        p_zombie_dies = max(0.02, p_zombie_dies - 0.02)

    return p_escape, p_infect, p_human_dies, p_zombie_dies


def _apply_outcome(
    outcome: Outcome,
    human: "Human",
    zombie: "Zombie",
    world: "World",
) -> None:
    """
    Applies the effects of a combat outcome using the Command pattern.

    Design Pattern: COMMAND
        Each outcome is encapsulated as a Command object. The command is
        executed through the world's CommandHistory (if available), which
        logs it for replay and post-game analytics. If no history exists
        the command is executed directly.

    Args:
        outcome: Result of the encounter.
        human: Human agent.
        zombie: Zombie agent.
        world: The shared world.

    References:
        https://refactoring.guru/design-patterns/command
    """
    tick = getattr(world, "tick", 0)

    # Build the appropriate command object
    command_map = {
        "escape":         EscapeCommand,
        "human_infected": InfectCommand,
        "human_dies":     KillHumanCommand,
        "zombie_dies":    KillZombieCommand,
    }

    cmd_class = command_map.get(outcome)
    if cmd_class is None:
        return

    command = cmd_class(human=human, zombie=zombie, world=world, tick=tick)

    # Execute through CommandHistory if the engine attached one
    history: Optional[CommandHistory] = getattr(world, "command_history", None)
    if history is not None:
        history.execute(command)
    else:
        command.execute()


