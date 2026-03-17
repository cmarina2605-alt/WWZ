"""
engine.py — Motor principal de la simulación Guerra Mundial J.

Engine es el orquestador central: crea el mundo, genera todos los agentes,
los coloca en el grid, lanza sus threads y gestiona el ciclo de vida
completo de la simulación.

Threads que gestiona:
    - Un thread por agente (humano o zombi) → lógica autónoma en Agent.run().
    - WinChecker   → comprueba condiciones de victoria cada WIN_CHECK_INTERVAL s.
    - TickCounter  → incrementa world.tick a la velocidad base de la simulación.
    - InfectionMonitor → detecta infectados y los convierte en zombis tras
                         INFECTION_DELAY_TICKS ticks de incubación.

Condiciones de victoria:
    Humanos ganan si: no quedan zombis, o antidote_ready está activo.
    Zombis ganan si:  no quedan humanos vivos.

Controles en tiempo real:
    pause() / resume() — suspenden/reanudan el loop de agentes.
    reset()            — detiene todo y limpia el estado para reiniciar.
    stop()             — señaliza game_over y espera que los threads terminen.

El Engine también expone get_snapshot() para que la UI acceda al estado
actual sin race conditions, y get_stats() para guardar resultados en la DB.
"""

import threading
import time
import random
from typing import List, Dict, Optional, Any

import config
from simulation.world import World
from agents.base_agent import game_over, antidote_ready, national_alert
from agents.human import Normal, Scientist, Military, Politician
from agents.zombie import Zombie


class Engine:
    """
    Motor central de la simulación.

    Responsabilidades:
    - Crear y posicionar agentes en el mundo.
    - Lanzar todos los threads de agentes.
    - Supervisar condiciones de victoria/derrota.
    - Exponer métodos de control: start, pause, reset.
    - Proveer snapshots del estado para la UI.

    Attributes:
        world (World): El mundo compartido.
        agents (List[Agent]): Lista de todos los agentes vivos.
        n_humans (int): Número de humanos vivos.
        n_zombies (int): Número de zombis vivos.
        tick (int): Tick actual de la simulación.
        running (bool): True si la simulación está en marcha.
        paused (bool): True si está en pausa.
        result (Optional[str]): "humans_win" | "zombies_win" | None.
        seed (int): Semilla aleatoria usada en esta simulación.
        strategy (str): Estrategia de comportamiento humano activa.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        strategy: str = "flee",
        n_humans: int = config.NUM_HUMANS,
        n_zombies: int = config.NUM_ZOMBIES,
        p_infect: float = config.P_INFECT,
    ) -> None:
        """
        Inicializa el motor con parámetros de simulación.

        Args:
            seed: Semilla aleatoria (None = aleatoria).
            strategy: Estrategia de comportamiento humano.
            n_humans: Número inicial de humanos.
            n_zombies: Número inicial de zombis.
            p_infect: Probabilidad de infección.
        """
        self.seed: int = seed if seed is not None else random.randint(0, 999999)
        random.seed(self.seed)

        self.strategy: str = strategy
        self.n_humans_initial: int = n_humans
        self.n_zombies_initial: int = n_zombies
        self.p_infect: float = p_infect

        self.world: World = World()
        self.agents: List[Any] = []
        self.n_humans: int = 0
        self.n_zombies: int = 0
        self.tick: int = 0
        self.running: bool = False
        self.paused: bool = False
        self.result: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        self._pause_event: threading.Event = threading.Event()
        self._pause_event.set()  # No pausado inicialmente
        self._win_thread: Optional[threading.Thread] = None
        self._tick_thread: Optional[threading.Thread] = None

        # Limpiar eventos globales
        game_over.clear()
        antidote_ready.clear()
        national_alert.clear()

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def start_simulation(self) -> None:
        """
        Crea todos los agentes, los posiciona y lanza sus threads.

        También inicia el thread de supervisión de condiciones de victoria,
        el thread del contador de ticks global y el monitor de infectados.
        """
        self._create_agents()
        self._start_all_threads()

        self.running = True
        self.start_time = time.time()

        # Evento narrativo de apertura: el origen del brote
        self.world.push_event(
            "outbreak",
            "🧪 José el Profe, harto de sus alumnos, ha creado la Fórmula Z...",
        )
        self.world.push_event(
            "outbreak",
            "🧟 ¡El experimento ha salido MAL! ¡José se convierte en zombi!",
        )

        # Thread de supervisión de victorias
        self._win_thread = threading.Thread(
            target=self._win_condition_loop, daemon=True, name="WinChecker"
        )
        self._win_thread.start()

        # Thread de tick global
        self._tick_thread = threading.Thread(
            target=self._tick_loop, daemon=True, name="TickCounter"
        )
        self._tick_thread.start()

        # Thread de conversión de infectados
        self._infection_thread = threading.Thread(
            target=self._infection_monitor_loop, daemon=True, name="InfectionMonitor"
        )
        self._infection_thread.start()

        # Thread de la mecánica Casa Blanca: espera alerta → elige estrategia
        self._strategy_thread = threading.Thread(
            target=self._strategy_monitor_loop, daemon=True, name="StrategyMonitor"
        )
        self._strategy_thread.start()

    def pause(self) -> None:
        """
        Pausa o reanuda la simulación.

        Activa/desactiva el evento de pausa. Los agentes comprueban
        este evento en su bucle run() para detenerse.
        """
        if self.paused:
            self._pause_event.set()
            self.paused = False
        else:
            self._pause_event.clear()
            self.paused = True

    def reset(self) -> None:
        """
        Detiene la simulación actual y reinicia el estado.

        Activa game_over para terminar todos los threads de agentes,
        limpia el mundo y resetea contadores.
        """
        game_over.set()
        time.sleep(0.5)  # Dar tiempo a los threads a terminar

        self.agents.clear()
        self.world = World()
        self.n_humans = 0
        self.n_zombies = 0
        self.tick = 0
        self.running = False
        self.paused = False
        self.result = None
        self.start_time = None
        self.end_time = None
        self.strategy = "none"

        game_over.clear()
        antidote_ready.clear()
        national_alert.clear()
        self._pause_event.set()

    def stop(self) -> None:
        """Detiene la simulación definitivamente."""
        game_over.set()
        self.running = False
        self.end_time = time.time()

    # ------------------------------------------------------------------
    # Creación de agentes
    # ------------------------------------------------------------------

    def _create_agents(self) -> None:
        """
        Crea y posiciona todos los agentes en el mundo.

        Distribuye roles según las constantes de configuración.
        """
        n = self.n_humans_initial
        # Escalar roles para que no superen el total de humanos
        n_sci = min(config.NUM_SCIENTISTS, max(0, n // 10))
        n_mil = min(config.NUM_MILITARY, max(0, n // 5))
        n_pol = min(config.NUM_POLITICIANS, max(0, n // 20))
        n_normal = max(0, n - n_sci - n_mil - n_pol)

        agent_specs = (
            [(Normal, {}) for _ in range(n_normal)] +
            [(Scientist, {"intelligence": random.randint(50, 100)}) for _ in range(n_sci)] +
            [(Military, {"ammo": random.randint(5, 20)}) for _ in range(n_mil)] +
            [(Politician, {"influence": random.randint(60, 100)}) for _ in range(n_pol)]
        )

        for AgentClass, kwargs in agent_specs:
            pos = self.world.find_free_cell()
            if pos is None:
                break
            agent = AgentClass(
                pos=pos,
                world=self.world,
                force=random.randint(30, 80),
                age=random.randint(18, 65),
                **kwargs,
            )
            self.world.place_agent(agent, pos)
            self.agents.append(agent)
            self.n_humans += 1

        # Crear zombis — el primero siempre es José y nace en San Diego
        for i in range(self.n_zombies_initial):
            if i == 0:
                # José aparece en San Diego (o en una celda libre cercana)
                outbreak = config.OUTBREAK_POS
                pos = outbreak if self.world.is_cell_free(outbreak) else self.world.find_free_cell()
            else:
                pos = self.world.find_free_cell()
            if pos is None:
                break
            zombie = Zombie(
                pos=pos,
                world=self.world,
                force=random.randint(50, 90),
            )
            self.world.place_agent(zombie, pos)
            self.agents.append(zombie)
            self.n_zombies += 1

    def _start_all_threads(self) -> None:
        """Inicia el thread de todos los agentes creados."""
        for agent in self.agents:
            agent.start()

    # ------------------------------------------------------------------
    # Bucles internos
    # ------------------------------------------------------------------

    def _tick_loop(self) -> None:
        """Incrementa el tick global del mundo a intervalos regulares."""
        while not game_over.is_set():
            self._pause_event.wait()
            time.sleep(config.TICK_SPEED)
            self.tick += 1
            self.world.tick = self.tick

    def _strategy_monitor_loop(self) -> None:
        """
        Implementa la mecánica 'mensaje a la Casa Blanca'.

        Flujo:
          1. Espera a que un Político active national_alert.
          2. Cuenta cuántas personas están en pánico (running) → más pánico,
             mensaje más rápido (la noticia se esparce sola).
          3. Espera delay_ticks antes de que la Casa Blanca 'responda'.
          4. Elige la estrategia según la influencia del político más poderoso.
          5. Escribe world.strategy para que todos los agentes la lean.
        """
        national_alert.wait()
        if game_over.is_set():
            return

        # Cuánta gente en pánico cuando llega la alerta
        num_alerted = sum(1 for a in self.agents if getattr(a, "state", "") == "running")
        delay_ticks = max(
            config.MIN_ALERT_DELAY,
            int(config.WHITEHOUSE_DELAY_BASE - config.WHITEHOUSE_DELAY_K * num_alerted),
        )

        self.world.push_event(
            "alert",
            f"📨 Mensaje en camino a Casa Blanca "
            f"({num_alerted} testigos) — llegará en ~{delay_ticks} ticks",
        )

        # Esperar los ticks de retardo
        start_tick = self.tick
        while self.tick - start_tick < delay_ticks and not game_over.is_set():
            time.sleep(0.2)
            self._pause_event.wait()

        if game_over.is_set():
            return

        # Elegir estrategia y activarla
        chosen = self._choose_strategy()
        self.strategy = chosen
        self.world.strategy = chosen

        self.world.push_event("strategy", f"🏛 Casa Blanca ha respondido")
        self.world.push_event("strategy", config.STRATEGY_DESCRIPTIONS.get(chosen, chosen))

    def _choose_strategy(self) -> str:
        """
        Elige la estrategia según la influencia del Político más poderoso.

        Escala de influencia (0-100):
            ≥ 85 → military_first  (gobierno fuerte, respuesta militar)
            ≥ 65 → flee            (evacuación organizada)
            ≥ 45 → group           (protección civil, agrupación)
            <  45 → random         (gobierno débil, nadie se pone de acuerdo)
        """
        politicians = [
            a for a in self.agents
            if isinstance(a, Politician) and a.is_alive()
        ]
        if not politicians:
            return "flee"

        max_influence = max(p.influence for p in politicians)

        if max_influence >= 85:
            return "military_first"
        elif max_influence >= 65:
            return "flee"
        elif max_influence >= 45:
            return "group"
        else:
            return "random"

    def _infection_monitor_loop(self) -> None:
        """
        Monitoriza agentes infectados y los convierte en zombis tras un retardo.

        Implementa el período de incubación: un humano infectado no se
        convierte inmediatamente, sino después de INFECTION_DELAY_TICKS ticks.
        Esto evita race conditions al delegar la creación del nuevo Zombie
        a un thread dedicado en lugar de hacerlo dentro del thread del agente.
        """
        infection_timers: dict = {}  # agent_id -> tick en que se infectó

        while not game_over.is_set():
            time.sleep(0.3)
            self._pause_event.wait()
            if game_over.is_set():
                break

            alive_ids: set = set()
            for agent in list(self.agents):
                alive_ids.add(agent.agent_id)
                if (
                    agent.state == "infected"
                    and agent.__class__.__name__ != "Zombie"
                    and agent.is_alive()
                ):
                    if agent.agent_id not in infection_timers:
                        # Primera vez que vemos este agente infectado
                        infection_timers[agent.agent_id] = self.tick
                    elif (
                        self.tick - infection_timers[agent.agent_id]
                        >= config.INFECTION_DELAY_TICKS
                    ):
                        # Período de incubación cumplido → convertir
                        infection_timers.pop(agent.agent_id, None)
                        if agent.is_alive():
                            self.convert_infected(agent)

            # Limpiar timers de agentes que ya no existen
            for aid in list(infection_timers.keys()):
                if aid not in alive_ids:
                    del infection_timers[aid]

    def _win_condition_loop(self) -> None:
        """
        Comprueba las condiciones de victoria/derrota periódicamente.

        Se ejecuta en un thread separado a intervalos de WIN_CHECK_INTERVAL.
        """
        while not game_over.is_set():
            time.sleep(config.WIN_CHECK_INTERVAL)
            self._pause_event.wait()
            self.check_win_conditions()

    def check_win_conditions(self) -> None:
        """
        Evalúa si la simulación ha terminado.

        Condiciones:
        - Humanos ganan: no quedan zombis.
        - Zombis ganan: no quedan humanos vivos (ni infectados).
        - Antídoto: antidote_ready activo → humanos ganan.
        """
        counts = self.world.count_agents_by_type()
        self.n_zombies = counts.get("Zombie", 0)
        living_humans = sum(
            1 for a in self.agents
            if a.__class__.__name__ != "Zombie" and a.is_alive()
            and a.state not in ("infected", "dead")
        )
        self.n_humans = living_humans

        if antidote_ready.is_set():
            self.result = "humans_win"
            self._end_simulation("humans_win")
            return

        if self.n_zombies == 0:
            self.result = "humans_win"
            self._end_simulation("humans_win")
        elif living_humans == 0:
            self.result = "zombies_win"
            self._end_simulation("zombies_win")

    def _end_simulation(self, result: str) -> None:
        """
        Finaliza la simulación con el resultado indicado.

        Args:
            result: "humans_win" o "zombies_win".
        """
        self.result = result
        self.end_time = time.time()
        game_over.set()
        self.running = False
        self.world.push_event(
            "simulation_end",
            f"Simulación terminada: {result} en tick {self.tick}",
        )

    # ------------------------------------------------------------------
    # Conversión de infectados
    # ------------------------------------------------------------------

    def convert_infected(self, human: Any) -> Zombie:
        """
        Convierte un humano infectado en zombi.

        Se ejecuta bajo el world.lock para evitar race conditions.

        Args:
            human: Agente humano infectado.

        Returns:
            El nuevo agente Zombie creado en la misma posición.
        """
        pos = human.pos
        human.die()

        zombie = Zombie(pos=pos, world=self.world, force=random.randint(50, 80))
        placed = self.world.place_agent(zombie, pos)
        if not placed:
            free = self.world.find_free_cell()
            if free:
                self.world.place_agent(zombie, free)

        self.agents.append(zombie)
        zombie.start()
        self.n_zombies += 1

        self.world.push_event("infection", f"💀 Humano {human.agent_id} se convierte en zombi")
        return zombie

    # ------------------------------------------------------------------
    # Snapshot para UI/DB
    # ------------------------------------------------------------------

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Retorna el estado actual de la simulación para la UI o la DB.

        Returns:
            Dict con contadores, tick, resultado y snapshot del grid.
        """
        infected_count = sum(
            1 for a in self.agents
            if a.state == "infected" and a.__class__.__name__ != "Zombie"
        )
        # Progreso del antídoto: el científico más avanzado
        antidote_pct = 0
        from agents.human import Scientist
        scientists_in_lab = [
            a for a in self.agents
            if isinstance(a, Scientist) and a.is_alive()
        ]
        if scientists_in_lab:
            best_progress = max(
                getattr(a, "antidote_progress", 0) for a in scientists_in_lab
            )
            antidote_pct = min(100, int(best_progress / max(1, config.ANTIDOTE_TICKS) * 100))

        return {
            "tick": self.tick,
            "n_humans": self.n_humans,
            "n_zombies": self.n_zombies,
            "infected": infected_count,
            "antidote_pct": antidote_pct,
            "result": self.result,
            "running": self.running,
            "paused": self.paused,
            "strategy": self.strategy,
            "seed": self.seed,
            "grid": self.world.get_state_snapshot(),
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estadísticas resumidas de la simulación actual.

        Returns:
            Dict con métricas de la simulación.
        """
        duration = (
            (self.end_time or time.time()) - (self.start_time or time.time())
        )
        return {
            "seed": self.seed,
            "tick": self.tick,
            "n_humans": self.n_humans,
            "n_zombies": self.n_zombies,
            "result": self.result,
            "duration": round(duration, 2),
            "strategy": self.strategy,
            "p_infect": self.p_infect,
        }
