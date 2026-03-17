"""
simulation — Paquete del motor de simulación Guerra Mundial J.

Contiene toda la lógica que hace correr la simulación:

    world.py    — El grid 2D compartido; todas las operaciones sobre él
                  están protegidas por threading.Lock.
    engine.py   — Orquestador: crea agentes, lanza threads, comprueba
                  condiciones de victoria y convierte infectados en zombis.
    movement.py — Cálculo de posiciones: huida de humanos, persecución de
                  zombis, random walk y propagación de pánico social.
    combat.py   — Resolución probabilística de encuentros humano↔zombi:
                  escape / infección / muerte del humano / muerte del zombi.

Flujo principal:
    Engine.start_simulation()
        → _create_agents()  → coloca agentes en el grid
        → _start_all_threads() → arranca un thread por agente
        → _win_condition_loop  → comprueba victoria cada WIN_CHECK_INTERVAL s
        → _tick_loop           → incrementa world.tick
        → _infection_monitor_loop → convierte infectados tras INFECTION_DELAY_TICKS
"""

from simulation.world import World
from simulation.engine import Engine

__all__ = [
    "World",
    "Engine",
]
