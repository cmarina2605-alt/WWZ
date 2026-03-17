"""
movement.py — Lógica de movimiento para agentes de la simulación.

Módulo de funciones puras (sin estado propio) que calculan la siguiente
posición de cada agente en función de su tipo y el estado del mundo.

Funciones principales:
    calculate_next_pos(agent, world)
        Dispatcher: llama a _human_next_pos o _zombie_next_pos según el tipo.

    _human_next_pos(human, world)
        Si hay zombis visibles, calcula el vector de huida opuesto al más
        cercano y añade ruido aleatorio para movimiento no determinista.
        Si no hay amenaza, hace random walk.

    _zombie_next_pos(zombie, world)
        Si tiene target_id guardado y lo localiza en el radio de visión,
        se mueve hacia él. Si no, random walk.

    move_towards(src, dst, world)
        Un paso normalizado de src hacia dst (usado por Military y Zombie).

    random_walk(pos, world, step=1)
        Desplazamiento aleatorio de hasta `step` celdas en cada eje.

    panic_spread(agent, world)
        Si ≥4 vecinos en radio 3 están en estado "running", el agente
        entra en pánico aunque no vea zombis (contagio social).

Utilidades internas:
    _flee_vector   — vector normalizado de huida opuesto a la amenaza.
    _dist          — distancia euclidiana entre dos puntos.
    _clamp         — mantiene coordenadas dentro de [0, size-1].
    _resolve_collision — busca celda libre si la destino está ocupada.
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
    Calcula la siguiente posición para un agente.

    Para humanos: vector de huida opuesto al zombi más cercano + ruido.
    Para zombis: hacia el objetivo o random walk.

    Args:
        agent: El agente que se va a mover.
        world: El mundo compartido.

    Returns:
        Tupla (x, y) de la siguiente posición.
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
    Calcula la siguiente posición para un humano según la estrategia activa.

    Estrategias (leídas de world.strategy):
        "none" / "flee" — huida del zombi más cercano + ruido (default).
                          En "flee", el vector se multiplica ×1.5 para huida
                          más agresiva una vez la Casa Blanca da la orden.
        "group"         — sin zombis cerca: moverse hacia el centroide de los
                          humanos vecinos (seguridad en el grupo). Con zombis: huir.
        "military_first"— civiles sin zombis cerca siguen al militar más cercano.
                          Con zombis: huir. Los militares lo gestionan en su update().
        "random"        — random walk independientemente de los zombis.
                          Representa el caos cuando el gobierno no se coordina.

    Args:
        human: El agente humano.
        world: El mundo compartido.

    Returns:
        Nueva posición (x, y).
    """
    strategy = getattr(world, "strategy", "none")

    # Estrategia RANDOM: caos total, ignora zombis
    if strategy == "random":
        return random_walk(human.pos, world)

    nearby = world.get_agents_in_radius(human.pos, config.VISION_HUMAN)
    zombies = [a for a in nearby if a.__class__.__name__ == "Zombie"]

    if not zombies:
        # Sin peligro inmediato: aplicar movimiento estratégico
        if strategy == "group":
            return _group_movement(human, nearby, world)
        elif strategy == "military_first":
            return _escort_military(human, nearby, world)
        else:
            return random_walk(human.pos, world)

    # Con zombis cerca: siempre huir, pero con intensidad distinta según estrategia
    closest = min(zombies, key=lambda z: _dist(human.pos, z.pos))
    flee_vec = _flee_vector(human.pos, closest.pos)

    # "flee" activo: huida más agresiva (vector ×1.5)
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
    Mueve al humano hacia el centroide de los humanos cercanos (estrategia GROUP).

    La idea: seguridad en el grupo. Si hay suficientes vecinos, el humano
    se desplaza hacia su centro de masa. Si está solo, camina aleatoriamente.

    Args:
        human: El agente que se mueve.
        nearby: Agentes ya calculados en el radio de visión.
        world: El mundo compartido.

    Returns:
        Nueva posición (x, y).
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
    Mueve a los civiles hacia el militar más cercano (estrategia MILITARY_FIRST).

    Los militares no usan esta función — su update() los envía a cazar zombis.
    Los civiles sin militar visible caminan aleatoriamente.

    Args:
        human: El agente civil que se mueve.
        nearby: Agentes ya calculados en el radio de visión.
        world: El mundo compartido.

    Returns:
        Nueva posición (x, y).
    """
    from agents.human import Military

    # Los militares tienen su propia lógica de movimiento en update()
    if isinstance(human, Military):
        return random_walk(human.pos, world)

    militaries = [a for a in nearby if isinstance(a, Military) and a.is_alive()]
    if not militaries:
        return random_walk(human.pos, world)

    closest_mil = min(militaries, key=lambda m: _dist(human.pos, m.pos))
    return move_towards(human.pos, closest_mil.pos, world)


def _zombie_next_pos(zombie: "Agent", world: "World") -> Tuple[int, int]:
    """
    Calcula la siguiente posición para un zombi.

    Si tiene un target_id válido, se mueve hacia él.
    Si no, hace random walk.

    Args:
        zombie: El agente zombi.
        world: El mundo compartido.

    Returns:
        Nueva posición (x, y).
    """
    from agents.human import Human

    if zombie.target_id is not None:
        # Buscar al objetivo
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
    Calcula un paso hacia una posición destino.

    Args:
        src: Posición origen (x, y).
        dst: Posición destino (x, y).
        world: El mundo para comprobar límites.

    Returns:
        Nueva posición (x, y) un paso más cerca de dst.
    """
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    dist = math.sqrt(dx * dx + dy * dy)

    if dist < 1:
        return src

    # Normalizar y redondear
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
    Calcula una posición adyacente aleatoria.

    Args:
        pos: Posición actual (x, y).
        world: El mundo para comprobar límites.
        step: Máximo desplazamiento en cada eje.

    Returns:
        Nueva posición (x, y) adyacente.
    """
    dx = random.randint(-step, step)
    dy = random.randint(-step, step)
    new_pos = _clamp((pos[0] + dx, pos[1] + dy), world.size)
    return new_pos


def panic_spread(agent: "Agent", world: "World") -> None:
    """
    Propaga el pánico entre agentes cercanos.

    Si un agente tiene ≥4 vecinos en estado "running", entra también
    en estado "running" independientemente de si ve zombis.

    Args:
        agent: El agente que puede entrar en pánico.
        world: El mundo compartido.
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
# Utilidades internas
# ---------------------------------------------------------------------------

def _flee_vector(
    pos: Tuple[int, int],
    threat_pos: Tuple[int, int],
) -> Tuple[float, float]:
    """
    Calcula el vector de dirección opuesta a una amenaza.

    Args:
        pos: Posición del agente que huye.
        threat_pos: Posición de la amenaza.

    Returns:
        Vector normalizado de huida (dx, dy).
    """
    dx = pos[0] - threat_pos[0]
    dy = pos[1] - threat_pos[1]
    dist = math.sqrt(dx * dx + dy * dy)

    if dist < 1e-6:
        # Misma posición: huir en dirección aleatoria
        angle = random.uniform(0, 2 * math.pi)
        return (math.cos(angle), math.sin(angle))

    return (dx / dist, dy / dist)


def _dist(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Distancia euclidiana entre dos puntos."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _clamp(pos: Tuple[int, int], size: int) -> Tuple[int, int]:
    """Asegura que pos está dentro de [0, size-1]."""
    return (max(0, min(size - 1, pos[0])), max(0, min(size - 1, pos[1])))


def _resolve_collision(
    pos: Tuple[int, int],
    agent: "Agent",
    world: "World",
) -> Tuple[int, int]:
    """
    Si la celda destino está ocupada, busca una celda libre adyacente.

    Args:
        pos: Posición destino deseada.
        agent: El agente que se mueve.
        world: El mundo.

    Returns:
        La posición libre más cercana o la posición actual si no hay ninguna.
    """
    if world.is_cell_free(pos):
        return pos

    # Intentar posiciones adyacentes
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            candidate = _clamp((pos[0] + dx, pos[1] + dy), world.size)
            if world.is_cell_free(candidate):
                return candidate

    # Si todo está ocupado, quedarse en el sitio
    return agent.pos
