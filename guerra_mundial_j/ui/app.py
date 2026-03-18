"""
app.py — Main Tkinter application window.

App is the Tk root window that orchestrates all visual widgets
and acts as a bridge between the UI and the simulation Engine.

Layout:
    ┌─────────────────────────┬───────────────────────┐
    │      GridCanvas         │  ControlPanel         │
    │      (600×600 px)       │  StatsPanel           │
    │                         │  EventLog             │
    └─────────────────────────┴───────────────────────┘

UI loop (every UI_REFRESH_MS = 100 ms):
    1. engine.get_snapshot() → gets the current state in a thread-safe manner.
    2. grid_canvas.render()  → draws agents on the grid.
    3. stats_panel.update()  → refreshes counters (humans, zombies,
       infected, antidote progress, tick, strategy, result).
    4. world.pop_events()    → consumes and displays new events in the EventLog.

User actions (called from ControlPanel):
    action_start()     — starts the simulation if not running.
    action_pause()     — pauses / resumes.
    action_reset()     — resets the world and UI.
    action_run_batch() — launches N headless simulations in a daemon thread
                         and saves results to the database.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, TYPE_CHECKING

import config

if TYPE_CHECKING:
    from simulation.engine import Engine


class App(tk.Tk):
    """
    Main window for the Guerra Mundial J simulation.

    Layout:
        ┌─────────────────────────┬───────────────────────┐
        │      GridCanvas         │  ControlPanel         │
        │      (600x600)          │  EventLog             │
        │                         │  StatsPanel           │
        └─────────────────────────┴───────────────────────┘

    The UI update loop runs via self.after() every UI_REFRESH_MS
    milliseconds, calling update_ui().

    Attributes:
        engine (Engine): Associated simulation engine.
        grid_canvas (GridCanvas): Grid canvas.
        control_panel (ControlPanel): Controls panel.
        event_log (EventLog): Event log.
        stats_panel (StatsPanel): Statistics panel.
    """

    def __init__(self, engine: "Engine") -> None:
        """
        Initializes the main window.

        Args:
            engine: Simulation engine instance.
        """
        super().__init__()
        self.engine: "Engine" = engine
        self.title("⚠️  Guerra Mundial J — Humans vs Zombies Simulation")
        self.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.resizable(False, False)
        self.configure(bg="#0d0d1a")

        self._last_result: Optional[str] = None

        self._build_layout()
        self._start_ui_loop()

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        """Builds the main window layout."""
        from ui.grid_canvas import GridCanvas
        from ui.control_panel import ControlPanel
        from ui.event_log import EventLog
        from ui.stats_panel import StatsPanel
        from ui.chart import PopulationChart

        # ── Left column: canvas ──────────────────────────────────────
        left_frame = tk.Frame(self, bg="#0d0d1a", padx=6, pady=6)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        self.grid_canvas = GridCanvas(left_frame, size=config.CANVAS_SIZE)
        self.grid_canvas.pack()

        # Thin separator
        tk.Frame(self, bg="#1e2a4a", width=2).pack(side=tk.LEFT, fill=tk.Y)

        # ── Right column ─────────────────────────────────────────────
        right_frame = tk.Frame(
            self,
            bg="#0d1117",
            padx=8,
            pady=6,
            width=config.WINDOW_WIDTH - config.CANVAS_SIZE - 22,
        )
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        right_frame.pack_propagate(False)

        self.control_panel = ControlPanel(right_frame, app=self)
        self.control_panel.pack(fill=tk.X, pady=(0, 4))

        tk.Frame(right_frame, bg="#1e2a4a", height=1).pack(fill=tk.X, pady=2)

        self.stats_panel = StatsPanel(right_frame)
        self.stats_panel.pack(fill=tk.X, pady=(0, 4))

        tk.Frame(right_frame, bg="#1e2a4a", height=1).pack(fill=tk.X, pady=2)

        self.chart = PopulationChart(right_frame, chart_height=90)
        self.chart.pack(fill=tk.X, pady=(0, 4))

        tk.Frame(right_frame, bg="#1e2a4a", height=1).pack(fill=tk.X, pady=2)

        self.event_log = EventLog(right_frame)
        self.event_log.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # UI loop
    # ------------------------------------------------------------------

    def _start_ui_loop(self) -> None:
        """Starts the UI update loop."""
        self.after(config.UI_REFRESH_MS, self._ui_loop)

    def _ui_loop(self) -> None:
        """
        Periodic UI update callback.

        Gets a snapshot from the engine, passes it to GridCanvas for
        rendering, and updates the stats and event panels.
        """
        try:
            self.update_ui()
        except Exception as exc:
            # Don't let a UI error bring down the window
            print(f"[UI] Error in update_ui: {exc}")
        finally:
            self.after(config.UI_REFRESH_MS, self._ui_loop)

    def update_ui(self) -> None:
        """
        Updates all visual components with the current state.

        - Renders the grid with the engine snapshot.
        - Updates the statistics panel.
        - Feeds new data points to the population chart.
        - Displays new events in the log.
        - Shows the game-over overlay when the simulation ends.
        """
        snapshot = self.engine.get_snapshot()

        # Render grid
        self.grid_canvas.render(snapshot["grid"])

        # Update statistics
        antidote_pct = snapshot.get("antidote_pct", 0)
        antidote_str = (
            "READY!" if antidote_pct >= 100
            else f"{antidote_pct}%"
        )
        strategy = snapshot.get("strategy", "none")
        strategy_labels = {
            "none":           "—",
            "flee":           "EVACUATION",
            "group":          "GROUPING",
            "military_first": "MILITARY OFFENSIVE",
            "random":         "NO PROTOCOL",
        }
        self.stats_panel.update({
            "n_humans":  snapshot["n_humans"],
            "n_zombies": snapshot["n_zombies"],
            "infected":  snapshot.get("infected", 0),
            "tick":      snapshot["tick"],
            "phase":     snapshot.get("phase", "🧟 Outbreak"),
            "strategy":  strategy_labels.get(strategy, strategy),
            "antidote":  antidote_str,
            "result":    snapshot["result"] or "In progress",
        })

        # Feed population chart (every tick when running)
        if snapshot.get("running") or snapshot["tick"] > 0:
            self.chart.add_point(
                snapshot["n_humans"],
                snapshot["n_zombies"],
                snapshot.get("infected", 0),
            )

        # Game-over overlay
        result = snapshot.get("result")
        if result and result != self._last_result:
            self._last_result = result
            self.grid_canvas.show_game_over(result)

        # Display new events
        events = self.engine.world.pop_events()
        for event in events:
            self.event_log.add_event(event["description"])

    # ------------------------------------------------------------------
    # Control actions (called from ControlPanel)
    # ------------------------------------------------------------------

    def action_start(self) -> None:
        """Starts the simulation if not already running."""
        if not self.engine.running:
            self.engine.start_simulation()
            self.event_log.add_event("▶️ Simulation started")

    def action_pause(self) -> None:
        """Pauses or resumes the simulation."""
        self.engine.pause()
        state = "⏸ Paused" if self.engine.paused else "▶️ Resumed"
        self.event_log.add_event(state)

    def action_reset(self) -> None:
        """Resets the simulation."""
        self.engine.reset()
        self.grid_canvas.clear()
        self.grid_canvas.clear_overlay()
        self.chart.reset()
        self.stats_panel.reset()
        self._last_result = None
        self.event_log.add_event("🔄 Simulation reset")

    def action_run_batch(self, n: int = 100) -> None:
        """
        Runs n simulations in batch mode (without intermediate UI).

        Results are saved to the database.

        Args:
            n: Number of simulations to run.
        """
        from db.database import Database
        from db.stats import print_summary
        import threading

        def _batch():
            from simulation.engine import Engine
            db = Database()
            self.event_log.add_event(f"🔁 Starting batch of {n} simulations...")
            for i in range(n):
                eng = Engine()
                eng.start_simulation()
                # Esperar a que termine
                import time
                timeout = 60  # max seconds per simulation
                start = time.time()
                while eng.running and (time.time() - start) < timeout:
                    time.sleep(0.5)
                stats = eng.get_stats()
                db.save_simulation({
                    "seed": stats["seed"],
                    "p_infect": stats["p_infect"],
                    "strategy": stats["strategy"],
                    "result": stats["result"],
                    "duration": stats["duration"],
                    "humans_final": stats["n_humans"],
                    "zombies_final": stats["n_zombies"],
                    "tick_final": stats["tick"],
                })
                if (i + 1) % 10 == 0:
                    self.event_log.add_event(f"  Completed {i+1}/{n} simulations")
            print_summary(db)
            self.event_log.add_event(f"✅ Batch complete. See console for summary.")

        t = threading.Thread(target=_batch, daemon=True)
        t.start()
