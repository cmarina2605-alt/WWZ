"""
engine.py — Main engine for the Guerra Mundial J simulation.

Engine is the central orchestrator: it creates the world, generates all agents,
places them on the grid, starts their threads and manages the complete
lifecycle of the simulation.

Threads it manages:
    - One thread per agent (human or zombie) → autonomous logic in Agent.run().
    - WinChecker   → checks victory conditions every WIN_CHECK_INTERVAL s.
    - TickCounter  → increments world.tick at the base simulation speed.
    - InfectionMonitor → detects infected agents and turns them into zombies after
                         INFECTION_DELAY_TICKS ticks of incubation.

Victory conditions:
    Humans win if: no zombies remain, or antidote_ready is active.
    Zombies win if: no living humans remain.

Real-time controls:
    pause() / resume() — suspend/resume the agent loop.
    reset()            — stops everything and clears state for a restart.
    stop()             — signals game_over and waits for threads to finish.

Engine also exposes get_snapshot() so the UI can access the current state
without race conditions, and get_stats() to save results to the DB.
"""

import threading
import time
import random
from typing import List, Dict, Optional, Any

import config
from simulation.world import World
from agents.base_agent import game_over, antidote_ready, national_alert, pause_event
from agents.human import Normal, Scientist, Military, Politician
from agents.zombie import Zombie


class Engine:
    """
    Central simulation engine.

    Responsibilities:
    - Create and position agents in the world.
    - Launch all agent threads.
    - Monitor victory/defeat conditions.
    - Expose control methods: start, pause, reset.
    - Provide state snapshots for the UI.

    Attributes:
        world (World): The shared world.
        agents (List[Agent]): List of all living agents.
        n_humans (int): Number of living humans.
        n_zombies (int): Number of living zombies.
        tick (int): Current simulation tick.
        running (bool): True if the simulation is running.
        paused (bool): True if paused.
        result (Optional[str]): "humans_win" | "zombies_win" | None.
        seed (int): Random seed used in this simulation.
        strategy (str): Active human behavior strategy.
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
        Initializes the engine with simulation parameters.

        Args:
            seed: Random seed (None = random).
            strategy: Human behavior strategy.
            n_humans: Initial number of humans.
            n_zombies: Initial number of zombies.
            p_infect: Infection probability.
        """
        self.seed: int = seed if seed is not None else random.randint(0, 999999)
        random.seed(self.seed)

        self._default_strategy: str = strategy  # fallback used by _choose_strategy
        self.strategy: str = "none"             # set to "none" until White House responds
        self.phase: str = "🧟 Outbreak"   # Current narrative phase of the simulation
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

        self._win_thread: Optional[threading.Thread] = None
        self._tick_thread: Optional[threading.Thread] = None

        # Clear global events
        game_over.clear()
        antidote_ready.clear()
        national_alert.clear()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_simulation(self) -> None:
        """
        Creates all agents, positions them and starts their threads.

        Also starts the victory condition monitoring thread,
        the global tick counter thread and the infection monitor.
        """
        self._create_agents()
        self._start_all_threads()

        self.running = True
        self.start_time = time.time()

        # Opening narrative event: the origin of the outbreak
        self.world.push_event(
            "outbreak",
            "🧪 José the Teacher, fed up with his students, has created Formula Z...",
        )
        self.world.push_event(
            "outbreak",
            "🧟 The experiment went WRONG! José turns into a zombie!",
        )

        # Victory monitoring thread
        self._win_thread = threading.Thread(
            target=self._win_condition_loop, daemon=True, name="WinChecker"
        )
        self._win_thread.start()

        # Global tick thread
        self._tick_thread = threading.Thread(
            target=self._tick_loop, daemon=True, name="TickCounter"
        )
        self._tick_thread.start()

        # Infected conversion thread
        self._infection_thread = threading.Thread(
            target=self._infection_monitor_loop, daemon=True, name="InfectionMonitor"
        )
        self._infection_thread.start()

        # White House mechanic thread: waits for alert → chooses strategy
        self._strategy_thread = threading.Thread(
            target=self._strategy_monitor_loop, daemon=True, name="StrategyMonitor"
        )
        self._strategy_thread.start()

    def pause(self) -> None:
        """
        Pauses or resumes the simulation.

        Sets/clears the pause event. Agents check this event
        in their run() loop to stop.
        """
        if self.paused:
            pause_event.set()
            self.paused = False
        else:
            pause_event.clear()
            self.paused = True

    def reset(self) -> None:
        """
        Stops the current simulation and resets the state.

        Sets game_over to end all agent threads,
        clears the world and resets counters.
        """
        game_over.set()
        time.sleep(0.5)  # Give threads time to finish

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
        self.phase = "🧟 Outbreak"

        game_over.clear()
        antidote_ready.clear()
        national_alert.clear()
        pause_event.set()

    def stop(self) -> None:
        """Stops the simulation permanently."""
        pause_event.set()
        game_over.set()
        self.running = False
        self.end_time = time.time()

    # ------------------------------------------------------------------
    # Agent creation
    # ------------------------------------------------------------------

    def _create_agents(self) -> None:
        """
        Creates and positions all agents in the world.

        Distributes roles according to the configuration constants.
        """
        n = self.n_humans_initial
        # Scale roles proportionally to the total number of humans
        n_sci = max(1, n // 10)   # ~10% scientists
        n_mil = max(1, n // 5)    # ~20% military
        n_pol = max(1, n // 20)   # ~5% politicians
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

        # Create zombies — the first one is always José and spawns in San Diego
        for i in range(self.n_zombies_initial):
            if i == 0:
                # José appears in San Diego (or a nearby free cell)
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
        """Starts the thread of every created agent."""
        for agent in self.agents:
            agent.start()

    # ------------------------------------------------------------------
    # Internal loops
    # ------------------------------------------------------------------

    def _tick_loop(self) -> None:
        """Increments the global world tick at regular intervals."""
        while not game_over.is_set():
            pause_event.wait()
            time.sleep(config.TICK_SPEED)
            self.tick += 1
            self.world.tick = self.tick

    def _strategy_monitor_loop(self) -> None:
        """
        Implements the 'message to the White House' mechanic.

        Flow:
          1. Waits for a Politician to activate national_alert.
          2. Counts how many people are in panic (running) → more panic,
             faster message (the news spreads on its own).
          3. Waits delay_s real seconds before the White House 'responds'.
          4. Chooses the strategy based on the most influential politician.
          5. Writes world.strategy so all agents can read it.
        """
        national_alert.wait()
        if game_over.is_set():
            return

        # How many people are in panic when the alert arrives
        num_alerted = sum(1 for a in self.agents if getattr(a, "state", "") == "running")
        delay_s = max(
            config.MIN_ALERT_DELAY_S,
            config.WHITEHOUSE_DELAY_BASE_S - config.WHITEHOUSE_DELAY_K_S * num_alerted,
        )

        self.phase = "📨 Alert sent"
        self.world.push_event(
            "alert",
            f"📨 Message on its way to the White House "
            f"({num_alerted} in panic) — arriving in ~{int(delay_s)}s",
        )

        # Wait for the delay in real seconds (independent of simulation speed)
        deadline = time.time() + delay_s
        while time.time() < deadline and not game_over.is_set():
            time.sleep(0.2)
            pause_event.wait()

        if game_over.is_set():
            return

        # Choose strategy and activate it
        chosen, winner = self._choose_strategy()
        self.strategy = chosen
        self.world.strategy = chosen

        if winner:
            ideology_name = winner.IDEOLOGY_NAMES.get(winner.ideology, winner.ideology)
            self.phase = f"⚙ {ideology_name}"
            self.world.push_event(
                "strategy",
                f"🏛 The White House responds: {ideology_name} (influence {winner.influence}) imposes their agenda",
            )
        else:
            self.phase = "⚙ Protocol activated"
            self.world.push_event("strategy", "🏛 The White House has responded (no politicians alive)")
        self.world.push_event("strategy", config.STRATEGY_DESCRIPTIONS.get(chosen, chosen))

    def _choose_strategy(self):
        """
        Chooses the strategy based on the ideology of the most influential Politician.

        Each politician has a fixed ideology that maps directly to a strategy.
        The one with the highest influence who is alive wins.
        If there are no politicians, "flee" is used by default.

        Returns:
            Tuple (strategy_str, winning_politician_or_None).
        """
        politicians = [
            a for a in self.agents
            if isinstance(a, Politician) and a.is_alive()
        ]
        if not politicians:
            return self._default_strategy, None

        winner = max(politicians, key=lambda p: p.influence)
        chosen = winner.IDEOLOGY_STRATEGIES.get(winner.ideology, "flee")
        return chosen, winner

    def _infection_monitor_loop(self) -> None:
        """
        Monitors infected agents and converts them into zombies after a delay.

        Implements the incubation period: an infected human does not turn
        immediately, but after INFECTION_DELAY_TICKS ticks.
        This avoids race conditions by delegating the creation of the new Zombie
        to a dedicated thread instead of doing it inside the agent's thread.
        """
        infection_timers: dict = {}  # agent_id -> tick when infected

        while not game_over.is_set():
            time.sleep(0.3)
            pause_event.wait()
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
                        # First time we see this infected agent
                        infection_timers[agent.agent_id] = self.tick
                    elif (
                        self.tick - infection_timers[agent.agent_id]
                        >= config.INFECTION_DELAY_TICKS
                    ):
                        # Incubation period complete → convert
                        infection_timers.pop(agent.agent_id, None)
                        if agent.is_alive():
                            self.convert_infected(agent)

            # Clean up timers for agents that no longer exist
            for aid in list(infection_timers.keys()):
                if aid not in alive_ids:
                    del infection_timers[aid]

    def _win_condition_loop(self) -> None:
        """
        Checks victory/defeat conditions periodically.

        Runs in a separate thread at WIN_CHECK_INTERVAL intervals.
        """
        while not game_over.is_set():
            time.sleep(config.WIN_CHECK_INTERVAL)
            pause_event.wait()
            self.check_win_conditions()

    def check_win_conditions(self) -> None:
        """
        Evaluates whether the simulation has ended.

        Conditions:
        - Humans win: no zombies remain.
        - Zombies win: no living humans NOR infected agents remain
          (all have died or converted).
        - Antidote: antidote_ready active → humans win.

        Infected agents count as still-living humans until they convert;
        this avoids declaring defeat during the incubation period.
        """
        counts = self.world.count_agents_by_type()
        self.n_zombies = counts.get("Zombie", 0)

        # Living humans = healthy + infected (not yet converted)
        living_humans = sum(
            1 for a in self.agents
            if a.__class__.__name__ != "Zombie" and a.is_alive()
            and a.state != "dead"
        )
        # For the UI counter we show only the non-infected
        self.n_humans = sum(
            1 for a in self.agents
            if a.__class__.__name__ != "Zombie" and a.is_alive()
            and a.state not in ("infected", "dead")
        )

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
        Ends the simulation with the given result.

        Args:
            result: "humans_win" or "zombies_win".
        """
        self.result = result
        self.end_time = time.time()
        game_over.set()
        self.running = False
        self.world.push_event(
            "simulation_end",
            f"Simulation ended: {result} at tick {self.tick}",
        )

    # ------------------------------------------------------------------
    # Infected conversion
    # ------------------------------------------------------------------

    def convert_infected(self, human: Any) -> Zombie:
        """
        Converts an infected human into a zombie.

        Runs under world.lock to avoid race conditions.

        Args:
            human: Infected human agent.

        Returns:
            The new Zombie agent created at the same position.
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

        self.world.push_event("infection", f"💀 Human {human.agent_id} turns into a zombie")
        return zombie

    # ------------------------------------------------------------------
    # Snapshot for UI/DB
    # ------------------------------------------------------------------

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Returns the current simulation state for the UI or DB.

        Returns:
            Dict with counters, tick, result and grid snapshot.
        """
        infected_count = sum(
            1 for a in self.agents
            if a.state == "infected" and a.__class__.__name__ != "Zombie"
        )
        # Antidote progress: the most advanced scientist
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

        n_humans_live = sum(
            1 for a in self.agents
            if a.__class__.__name__ != "Zombie" and a.is_alive()
            and a.state not in ("infected", "dead")
        )

        return {
            "tick": self.tick,
            "n_humans": n_humans_live,
            "n_zombies": self.n_zombies,
            "infected": infected_count,
            "antidote_pct": antidote_pct,
            "result": self.result,
            "running": self.running,
            "paused": self.paused,
            "strategy": self.strategy,
            "phase": self.phase,
            "seed": self.seed,
            "grid": self.world.get_state_snapshot(),
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Returns summary statistics of the current simulation.

        Returns:
            Dict with simulation metrics.
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
