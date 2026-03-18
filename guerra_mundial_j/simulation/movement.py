"""
movement.py — Movement logic for simulation agents.

Module of pure functions (no internal state) that calculate the next
position of each agent based on its type and the world state.

Main functions:
    calculate_next_pos(agent, world)
        Dispatcher: calls _human_next_pos or _zombie_next_pos based on type.

    _human_next_pos(human, world)
        If zombies are visible, calculates the flee vector opposite to the
        closest one and adds random noise for non-deterministic movement.
        If no threat, does a random walk.

    _zombie_next_pos(zombie, world)
        If it has a stored target_id and finds it within vision radius,
        moves toward it. Otherwise, random walk.

    move_towards(src, dst, world)
        One normalized step from src toward dst (used by Military and Zombie).

    random_walk(pos, world, step=1)
        Random displacement of up to `step` cells per axis.

    panic_spread(agent, world)
        If ≥4 neighbors within radius 3 are in "running" state, the agent
        enters panic even without seeing zombies (social contagion).

Internal utilities:
    _flee_vector   — normalized flee vector opposite to the threat.
    _dist          — Euclidean distance between two points.
    _clamp         — keeps coordinates within [0, size-1].
    _resolve_collision — finds a free cell if the destination is occupied.
"""

import random
import math
from typing import Tuple, List, TYPE_CHECKING

import config

if TYPE_CHECKING:
    from agents.base_agent import Agent
    from simulation.world import World


def calculate_next_pos(
    agent: "Agent",
    world: "World",
) -> Tuple[int, int]:
    """
    Calculates the next position for an agent.

    For humans: flee vector opposite the closest zombie + noise.
    For zombies: toward the target or random walk.

    Args:
        agent: The agent that is going to move.
        world: The shared world.

    Returns:
        Tuple (x, y) of the next position.
    """
    from agents.human import Human
    from agents.zombie import Zombie

    if isinstance(agent, Human):
        return _human_next_pos(agent, world)
    elif isinstance(agent, Zombie):
        return _zombie_next_pos(agent, world)
    else:
        return random_walk(agent.pos, world)


def _human_next_pos(human: "Agent", world: "World") -> Tuple[int, int]:
    """
    Calculates the next position for a human based on the active strategy.

    Strategies (read from world.strategy):
        "none" / "flee" — flee from the closest zombie + noise (default).
                          In "flee", the vector is multiplied ×1.5 for more
                          aggressive fleeing once the White House gives the order.
        "group"         — no zombies nearby: move toward the centroid of
                          neighboring humans (safety in numbers). With zombies: flee.
        "military_first"— civilians without nearby zombies follow the closest military.
                          With zombies: flee. Military handle this in their update().
        "random"        — random walk regardless of zombies.
                          Represents chaos when the government can't coordinate.

    Args:
        human: The human agent.
        world: The shared world.

    Returns:
        New position (x, y).
    """
    strategy = getattr(world, "strategy", "none")

    # RANDOM strategy: total chaos, ignores zombies
    if strategy == "random":
        return random_walk(human.pos, world)

    nearby = world.get_agents_in_radius(human.pos, config.VISION_HUMAN)
    zombies = [a for a in nearby if a.__class__.__name__ == "Zombie"]

    if not zombies:
        # No immediate danger: apply strategic movement
        if strategy == "group":
            return _group_movement(human, nearby, world)
        elif strategy == "military_first":
            return _escort_military(human, nearby, world)
        else:
            return random_walk(human.pos, world)

    # Zombies nearby: always flee, but with different intensity depending on strategy
    closest = min(zombies, key=lambda z: _dist(human.pos, z.pos))
    flee_vec = _flee_vector(human.pos, closest.pos)

    # "flee" active: more aggressive fleeing (vector ×1.5)
    flee_mult = 1.5 if strategy == "flee" else 1.0

    noise_x = random.uniform(-0.5, 0.5)
    noise_y = random.uniform(-0.5, 0.5)
    raw_x = human.pos[0] + flee_vec[0] * flee_mult + noise_x
    raw_y = human.pos[1] + flee_vec[1] * flee_mult + noise_y

    new_pos = _clamp((round(raw_x), round(raw_y)), world.size)
    return _resolve_collision(new_pos, human, world)


def _group_movement(
    human: "Agent",
    nearby: List["Agent"],
    world: "World",
) -> Tuple[int, int]:
    """
    Moves the human toward the centroid of nearby humans (GROUP strategy).

    The idea: safety in numbers. If there are enough neighbors, the human
    moves toward their center of mass. If alone, walks randomly.

    Args:
        human: The moving agent.
        nearby: Agents already computed within the vision radius.
        world: The shared world.

    Returns:
        New position (x, y).
    """
    from agents.human import Human

    neighbors = [
        a for a in nearby
        if isinstance(a, Human) and a.is_alive() and a is not human
    ]
    if not neighbors:
        return random_walk(human.pos, world)

    cx = sum(a.pos[0] for a in neighbors) / len(neighbors)
    cy = sum(a.pos[1] for a in neighbors) / len(neighbors)
    return move_towards(human.pos, (round(cx), round(cy)), world)


def _escort_military(
    human: "Agent",
    nearby: List["Agent"],
    world: "World",
) -> Tuple[int, int]:
    """
    Moves civilians toward the closest military agent (MILITARY_FIRST strategy).

    Military agents don't use this function — their update() sends them to hunt zombies.
    Civilians without a visible military agent walk randomly.

    Args:
        human: The civilian agent that is moving.
        nearby: Agents already computed within the vision radius.
        world: The shared world.

    Returns:
        New position (x, y).
    """
    from agents.human import Military

    # Military agents have their own movement logic in update()
    if isinstance(human, Military):
        return random_walk(human.pos, world)

    militaries = [a for a in nearby if isinstance(a, Military) and a.is_alive()]
    if not militaries:
        return random_walk(human.pos, world)

    closest_mil = min(militaries, key=lambda m: _dist(human.pos, m.pos))
    return move_towards(human.pos, closest_mil.pos, world)


def _zombie_next_pos(zombie: "Agent", world: "World") -> Tuple[int, int]:
    """
    Calculates the next position for a zombie.

    If it has a valid target_id, it moves toward it.
    Otherwise, does a random walk.

    Args:
        zombie: The zombie agent.
        world: The shared world.

    Returns:
        New position (x, y).
    """
    from agents.human import Human

    if zombie.target_id is not None:
        # Search for the target
        nearby = world.get_agents_in_radius(zombie.pos, config.VISION_ZOMBIE)
        targets = [a for a in nearby if a.agent_id == zombie.target_id]
        if targets:
            target = targets[0]
            return move_towards(zombie.pos, target.pos, world)

    return random_walk(zombie.pos, world)


def move_towards(
    src: Tuple[int, int],
    dst: Tuple[int, int],
    world: "World",
) -> Tuple[int, int]:
    """
    Calculates one step toward a destination position.

    Args:
        src: Source position (x, y).
        dst: Destination position (x, y).
        world: The world for boundary checking.

    Returns:
        New position (x, y) one step closer to dst.
    """
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    dist = math.sqrt(dx * dx + dy * dy)

    if dist < 1:
        return src

    # Normalize and round
    step_x = dx / dist
    step_y = dy / dist
    new_x = src[0] + round(step_x)
    new_y = src[1] + round(step_y)

    return _clamp((new_x, new_y), world.size)


def random_walk(
    pos: Tuple[int, int],
    world: "World",
    step: int = 1,
) -> Tuple[int, int]:
    """
    Calculates a random adjacent position.

    Args:
        pos: Current position (x, y).
        world: The world for boundary checking.
        step: Maximum displacement per axis.

    Returns:
        New adjacent position (x, y).
    """
    dx = random.randint(-step, step)
    dy = random.randint(-step, step)
    new_pos = _clamp((pos[0] + dx, pos[1] + dy), world.size)
    return new_pos


def panic_spread(agent: "Agent", world: "World") -> None:
    """
    Spreads panic among nearby agents.

    If an agent has ≥4 neighbors in "running" state, it also enters
    "running" state regardless of whether it sees zombies.

    Args:
        agent: The agent that may enter panic.
        world: The shared world.
    """
    from agents.human import Human

    if not isinstance(agent, Human):
        return
    if agent.state in ("fighting", "dead", "infected"):
        return

    nearby = world.get_agents_in_radius(agent.pos, 3)
    running_count = sum(1 for a in nearby if a.state == "running")

    if running_count >= 4 and agent.state == "calm":
        agent.set_state("running")
        agent.fear = min(100, agent.fear + 20)


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _flee_vector(
    pos: Tuple[int, int],
    threat_pos: Tuple[int, int],
) -> Tuple[float, float]:
    """
    Calculates the direction vector opposite to a threat.

    Args:
        pos: Position of the fleeing agent.
        threat_pos: Position of the threat.

    Returns:
        Normalized flee vector (dx, dy).
    """
    dx = pos[0] - threat_pos[0]
    dy = pos[1] - threat_pos[1]
    dist = math.sqrt(dx * dx + dy * dy)

    if dist < 1e-6:
        # Same position: flee in a random direction
        angle = random.uniform(0, 2 * math.pi)
        return (math.cos(angle), math.sin(angle))

    return (dx / dist, dy / dist)


def _dist(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Euclidean distance between two points."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _clamp(pos: Tuple[int, int], size: int) -> Tuple[int, int]:
    """Ensures pos is within [0, size-1]."""
    return (max(0, min(size - 1, pos[0])), max(0, min(size - 1, pos[1])))


def _resolve_collision(
    pos: Tuple[int, int],
    agent: "Agent",
    world: "World",
) -> Tuple[int, int]:
    """
    If the destination cell is occupied, finds a free adjacent cell.

    Args:
        pos: Desired destination position.
        agent: The moving agent.
        world: The world.

    Returns:
        The nearest free position, or the current position if none is available.
    """
    if world.is_cell_free(pos):
        return pos

    # Try adjacent positions
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            candidate = _clamp((pos[0] + dx, pos[1] + dy), world.size)
            if world.is_cell_free(candidate):
                return candidate

    # If everything is occupied, stay in place
    return agent.pos
