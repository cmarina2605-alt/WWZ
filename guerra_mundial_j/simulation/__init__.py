"""
simulation — Guerra Mundial J simulation engine package.

Contains all the logic that runs the simulation:

    world.py    — The shared 2D grid; all operations on it are
                  protected by threading.Lock.
    engine.py   — Orchestrator: creates agents, launches threads, checks
                  victory conditions and converts infected agents into zombies.
    movement.py — Position calculation: human fleeing, zombie chasing,
                  random walk and social panic propagation.
    combat.py   — Probabilistic resolution of human↔zombie encounters:
                  escape / infection / human death / zombie death.

Main flow:
    Engine.start_simulation()
        → _create_agents()  → places agents on the grid
        → _start_all_threads() → starts one thread per agent
        → _win_condition_loop  → checks victory every WIN_CHECK_INTERVAL s
        → _tick_loop           → increments world.tick
        → _infection_monitor_loop → converts infected after INFECTION_DELAY_TICKS
"""

from simulation.world import World
from simulation.engine import Engine

__all__ = [
    "World",
    "Engine",
]
