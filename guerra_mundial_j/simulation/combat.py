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
from typing import Literal, TYPE_CHECKING

import config

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
    p_escape = config.P_ESCAPE * force_ratio
    p_escape = min(0.7, max(0.05, p_escape))

    # Infection probability
    p_infect = config.P_INFECT
    if human.age > config.AGE_PENALTY_THRESHOLD:
        p_infect += 0.1  # More vulnerable if elderly

    # Probability that the human dies directly (scales down as p_infect increases)
    p_human_dies = max(0.0, (0.3 - force_ratio * 0.2) * (1 - config.P_INFECT))

    # Probability that the zombie dies (Military with ammo only)
    p_zombie_dies = config.P_KILL_ZOMBIE
    if isinstance(human, Military) and human.ammo > 0:
        p_zombie_dies += 0.15   # Guns help but zombies are hard to kill
        human.use_ammo()
    elif not isinstance(human, Military):
        p_zombie_dies = max(0.01, p_zombie_dies - 0.03)

    return p_escape, p_infect, p_human_dies, p_zombie_dies


def _apply_outcome(
    outcome: Outcome,
    human: "Human",
    zombie: "Zombie",
    world: "World",
) -> None:
    """
    Applies the effects of a combat outcome to the agents.

    Args:
        outcome: Result of the encounter.
        human: Human agent.
        zombie: Zombie agent.
        world: The shared world.
    """
    from simulation.engine import Engine  # Deferred import to avoid circular dependency

    if outcome == "escape":
        human.set_state("running")
        world.push_event("escape", f"🏃 Human {human.agent_id} escaped from Zombie {zombie.agent_id}")

    elif outcome == "human_infected":
        human.infect()
        world.push_event(
            "infection",
            f"🧟 Human {human.agent_id} infected by Zombie {zombie.agent_id}",
        )
        # The actual conversion is managed by Engine when it detects the "infected" state
        # to avoid concurrency issues when creating new threads

    elif outcome == "human_dies":
        human.die()
        world.push_event("death", f"💀 Human {human.agent_id} died at the hands of Zombie {zombie.agent_id}")

    elif outcome == "zombie_dies":
        zombie.die()
        world.push_event("zombie_death", f"🔫 Zombie {zombie.agent_id} eliminated by Human {human.agent_id}")


def combat_summary(outcome: Outcome, human_id: int, zombie_id: int) -> str:
    """
    Generates a human-readable description of the combat outcome.

    Args:
        outcome: Result of the encounter.
        human_id: Human ID.
        zombie_id: Zombie ID.

    Returns:
        Descriptive string of the event.
    """
    messages = {
        "escape": f"Human #{human_id} escaped from Zombie #{zombie_id}",
        "human_infected": f"Human #{human_id} was infected by Zombie #{zombie_id}",
        "human_dies": f"Human #{human_id} died facing Zombie #{zombie_id}",
        "zombie_dies": f"Zombie #{zombie_id} was eliminated by Human #{human_id}",
    }
    return messages.get(outcome, f"Unknown encounter between #{human_id} and #{zombie_id}")
