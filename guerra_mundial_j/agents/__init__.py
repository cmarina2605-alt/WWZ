"""
agents — Paquete de agentes de la simulación Guerra Mundial J.

Contiene todas las clases que representan entidades que se mueven y
actúan en el grid. Cada agente corre en su propio thread (hereda de
threading.Thread) y ejecuta su lógica en un bucle tick a tick.

Jerarquía de clases:
    Agent  (base_agent.py) — clase abstracta, gestiona el ciclo de vida
    ├── Human  (human.py)  — humano base con miedo y empatía
    │   ├── Normal         — ciudadano corriente, solo huye
    │   ├── Scientist      — navega al laboratorio y trabaja en el antídoto
    │   ├── Military       — persigue zombis activamente si tiene fuerza suficiente
    │   └── Politician     — emite alertas nacionales al detectar zombis
    └── Zombie (zombie.py) — persigue al humano más cercano; random walk si no ve ninguno

Señales globales compartidas (threading.Event):
    game_over      — detiene todos los threads cuando la partida acaba
    antidote_ready — activa la condición de victoria humana
    national_alert — activa la respuesta política/militar

Exporta las clases principales para imports directos desde `agents`.
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
