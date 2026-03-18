"""
agents — Guerra Mundial J simulation agents package.

Contains all classes representing entities that move and act on the grid.
Each agent runs in its own thread (inherits from threading.Thread) and
executes its logic in a tick-by-tick loop.

Class hierarchy:
    Agent  (base_agent.py) — abstract class, manages the lifecycle
    ├── Human  (human.py)  — base human with fear and empathy
    │   ├── Normal         — ordinary citizen, only flees
    │   ├── Scientist      — navigates to the lab and works on the antidote
    │   ├── Military       — actively chases zombies if strong enough
    │   └── Politician     — issues national alerts when detecting zombies
    └── Zombie (zombie.py) — chases the nearest human; random walk if none visible

Shared global signals (threading.Event):
    game_over      — stops all threads when the game ends
    antidote_ready — activates the human victory condition
    national_alert — activates the political/military response

Exports the main classes for direct imports from `agents`.
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
