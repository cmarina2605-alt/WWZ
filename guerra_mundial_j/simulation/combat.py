"""
combat.py — Resolución de encuentros entre humanos y zombis.

Cuando un humano y un zombi se encuentran en la misma celda o adyacentes,
este módulo calcula probabilísticamente el resultado del enfrentamiento.

Resultados posibles (Outcome):
    "escape"         — el humano logra huir (set_state "running").
    "human_infected" — el humano se infecta (human.infect()); el Engine
                       lo convertirá en zombi tras el período de incubación.
    "human_dies"     — el humano muere directamente (human.die()).
    "zombie_dies"    — el zombi es eliminado (zombie.die()).

Factores que influyen en las probabilidades:
    - force_ratio (humano / zombi): más fuerza relativa → más fácil escapar.
    - age: si el humano supera AGE_PENALTY_THRESHOLD, aumenta p_infect.
    - role: Military con munición suma +0.3 a p_zombie_dies; los no-militares
      tienen p_zombie_dies reducida.
    - Aleatoriedad base: el resultado siempre tiene componente aleatorio para
      que la simulación sea impredecible.

Todos los efectos (morir, infectar, huir) se aplican directamente sobre
los agentes, y se pushea un evento descriptivo al EventLog del world.
"""

import random
from typing import Literal, TYPE_CHECKING

import config

if TYPE_CHECKING:
    from agents.human import Human
    from agents.zombie import Zombie
    from simulation.world import World

# Tipo de resultado de un encuentro
Outcome = Literal["escape", "human_dies", "human_infected", "zombie_dies"]


def resolve_encounter(
    human: "Human",
    zombie: "Zombie",
    world: "World",
) -> Outcome:
    """
    Resuelve un encuentro entre un humano y un zombi.

    La probabilidad de cada resultado depende de:
    - force del humano y del zombi.
    - age del humano (penalización si es mayor).
    - role del humano (Military tiene bonus).
    - Aleatoriedad base.

    Los efectos secundarios se aplican directamente sobre los agentes
    bajo world.lock cuando es necesario.

    Args:
        human: El agente humano involucrado.
        zombie: El agente zombi involucrado.
        world: El mundo compartido (para conversiones).

    Returns:
        Outcome: Resultado del encuentro.
    """
    # Calcular probabilidades base
    p_escape, p_infect, p_human_dies, p_zombie_dies = _calculate_probabilities(
        human, zombie
    )

    # Normalizar (deben sumar 1)
    total = p_escape + p_infect + p_human_dies + p_zombie_dies
    if total <= 0:
        return "escape"

    p_escape /= total
    p_infect /= total
    p_human_dies /= total
    p_zombie_dies /= total

    # Seleccionar resultado
    roll = random.random()
    if roll < p_zombie_dies:
        outcome: Outcome = "zombie_dies"
    elif roll < p_zombie_dies + p_escape:
        outcome = "escape"
    elif roll < p_zombie_dies + p_escape + p_infect:
        outcome = "human_infected"
    else:
        outcome = "human_dies"

    # Aplicar efectos del resultado
    _apply_outcome(outcome, human, zombie, world)
    return outcome


def _calculate_probabilities(
    human: "Human",
    zombie: "Zombie",
) -> tuple[float, float, float, float]:
    """
    Calcula las probabilidades brutas de cada resultado.

    Args:
        human: Agente humano.
        zombie: Agente zombi.

    Returns:
        Tupla (p_escape, p_infect, p_human_dies, p_zombie_dies).
    """
    from agents.human import Military

    # Fuerza relativa
    force_ratio = human.force / max(1, zombie.force)

    # Probabilidad base de escape (más fuerza → más fácil escapar)
    p_escape = config.P_ESCAPE * force_ratio
    p_escape = min(0.7, max(0.05, p_escape))

    # Probabilidad de infección
    p_infect = config.P_INFECT
    if human.age > config.AGE_PENALTY_THRESHOLD:
        p_infect += 0.1  # Más vulnerable si es mayor

    # Probabilidad de que el humano muera directamente
    p_human_dies = max(0.05, 0.3 - force_ratio * 0.2)

    # Probabilidad de que el zombi muera (solo Military con munición)
    p_zombie_dies = config.P_KILL_ZOMBIE
    if isinstance(human, Military) and human.ammo > 0:
        p_zombie_dies += 0.3
        human.use_ammo()
    elif not isinstance(human, Military):
        p_zombie_dies = max(0.01, p_zombie_dies - 0.1)

    return p_escape, p_infect, p_human_dies, p_zombie_dies


def _apply_outcome(
    outcome: Outcome,
    human: "Human",
    zombie: "Zombie",
    world: "World",
) -> None:
    """
    Aplica los efectos de un resultado de combate sobre los agentes.

    Args:
        outcome: Resultado del encuentro.
        human: Agente humano.
        zombie: Agente zombi.
        world: El mundo compartido.
    """
    from simulation.engine import Engine  # Import diferido para evitar circular

    if outcome == "escape":
        human.set_state("running")
        world.push_event("escape", f"🏃 Humano {human.agent_id} escapó de Zombi {zombie.agent_id}")

    elif outcome == "human_infected":
        human.infect()
        world.push_event(
            "infection",
            f"🧟 Humano {human.agent_id} infectado por Zombi {zombie.agent_id}",
        )
        # La conversión real la gestiona Engine cuando detecta el estado "infected"
        # para evitar problemas de concurrencia al crear nuevos threads

    elif outcome == "human_dies":
        human.die()
        world.push_event("death", f"💀 Humano {human.agent_id} murió a manos de Zombi {zombie.agent_id}")

    elif outcome == "zombie_dies":
        zombie.die()
        world.push_event("zombie_death", f"🔫 Zombi {zombie.agent_id} eliminado por Humano {human.agent_id}")


def combat_summary(outcome: Outcome, human_id: int, zombie_id: int) -> str:
    """
    Genera una descripción legible del resultado de combate.

    Args:
        outcome: Resultado del encuentro.
        human_id: ID del humano.
        zombie_id: ID del zombi.

    Returns:
        Cadena descriptiva del evento.
    """
    messages = {
        "escape": f"Humano #{human_id} escapó de Zombi #{zombie_id}",
        "human_infected": f"Humano #{human_id} fue infectado por Zombi #{zombie_id}",
        "human_dies": f"Humano #{human_id} murió frente a Zombi #{zombie_id}",
        "zombie_dies": f"Zombi #{zombie_id} fue eliminado por Humano #{human_id}",
    }
    return messages.get(outcome, f"Encuentro desconocido entre #{human_id} y #{zombie_id}")
