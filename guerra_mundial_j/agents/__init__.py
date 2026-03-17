"""
agents — Paquete de agentes de la simulación.

Exporta las clases principales para que otros módulos puedan importar
directamente desde `agents` sin conocer la estructura interna.
"""

from agents.base_agent import Agent
from agents.human import Human, Normal, Scientist, Military, Politician
from agents.zombie import Zombie

__all__ = [
    "Agent",
    "Human",
    "Normal",
    "Scientist",
    "Military",
    "Politician",
    "Zombie",
]
