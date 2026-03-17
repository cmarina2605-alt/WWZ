"""
app.py — Ventana principal de la aplicación Tkinter.

App es el Tk root window que orquesta todos los widgets visuales
y actúa de puente entre la UI y el Engine de simulación.

Layout:
    ┌─────────────────────────┬───────────────────────┐
    │      GridCanvas         │  ControlPanel         │
    │      (600×600 px)       │  StatsPanel           │
    │                         │  EventLog             │
    └─────────────────────────┴───────────────────────┘

Loop de UI (cada UI_REFRESH_MS = 100 ms):
    1. engine.get_snapshot() → obtiene el estado actual de forma thread-safe.
    2. grid_canvas.render()  → pinta los agentes en el grid.
    3. stats_panel.update()  → refresca contadores (humanos, zombis,
       infectados, progreso del antídoto, tick, estrategia, resultado).
    4. world.pop_events()    → consume y muestra eventos nuevos en el EventLog.

Acciones del usuario (llamadas desde ControlPanel):
    action_start()     — inicia la simulación si no está en marcha.
    action_pause()     — pausa / reanuda.
    action_reset()     — reinicia el mundo y la UI.
    action_run_batch() — lanza N simulaciones headless en un thread daemon
                         y guarda los resultados en la base de datos.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, TYPE_CHECKING

import config

if TYPE_CHECKING:
    from simulation.engine import Engine


class App(tk.Tk):
    """
    Ventana principal de la simulación Guerra Mundial J.

    Layout:
        ┌─────────────────────────┬───────────────────────┐
        │      GridCanvas         │  ControlPanel         │
        │      (600x600)          │  EventLog             │
        │                         │  StatsPanel           │
        └─────────────────────────┴───────────────────────┘

    El loop de actualización de la UI se ejecuta con self.after()
    cada UI_REFRESH_MS milisegundos, llamando a update_ui().

    Attributes:
        engine (Engine): Motor de simulación asociado.
        grid_canvas (GridCanvas): Canvas del grid.
        control_panel (ControlPanel): Panel de controles.
        event_log (EventLog): Log de eventos.
        stats_panel (StatsPanel): Panel de estadísticas.
    """

    def __init__(self, engine: "Engine") -> None:
        """
        Inicializa la ventana principal.

        Args:
            engine: Instancia del motor de simulación.
        """
        super().__init__()
        self.engine: "Engine" = engine
        self.title("⚠️  Guerra Mundial J — Simulación Humanos vs Zombis")
        self.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")

        self._build_layout()
        self._start_ui_loop()

    # ------------------------------------------------------------------
    # Construcción del layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        """Construye el layout principal de la ventana."""
        from ui.grid_canvas import GridCanvas
        from ui.control_panel import ControlPanel
        from ui.event_log import EventLog
        from ui.stats_panel import StatsPanel

        # Frame izquierdo: grid
        left_frame = tk.Frame(self, bg="#1a1a2e", padx=5, pady=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        self.grid_canvas = GridCanvas(left_frame, size=config.CANVAS_SIZE)
        self.grid_canvas.pack()

        # Frame derecho: controles + log + stats
        right_frame = tk.Frame(
            self,
            bg="#16213e",
            padx=8,
            pady=8,
            width=config.WINDOW_WIDTH - config.CANVAS_SIZE - 20,
        )
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        right_frame.pack_propagate(False)

        self.control_panel = ControlPanel(right_frame, app=self)
        self.control_panel.pack(fill=tk.X, pady=(0, 5))

        self.stats_panel = StatsPanel(right_frame)
        self.stats_panel.pack(fill=tk.X, pady=(0, 5))

        self.event_log = EventLog(right_frame)
        self.event_log.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Loop de UI
    # ------------------------------------------------------------------

    def _start_ui_loop(self) -> None:
        """Inicia el loop de actualización de la UI."""
        self.after(config.UI_REFRESH_MS, self._ui_loop)

    def _ui_loop(self) -> None:
        """
        Callback periódico de actualización de la UI.

        Obtiene un snapshot del motor, lo pasa al GridCanvas para
        renderizado y actualiza los paneles de stats y eventos.
        """
        try:
            self.update_ui()
        except Exception as exc:
            # No dejar que un error en la UI derribe la ventana
            print(f"[UI] Error en update_ui: {exc}")
        finally:
            self.after(config.UI_REFRESH_MS, self._ui_loop)

    def update_ui(self) -> None:
        """
        Actualiza todos los componentes visuales con el estado actual.

        - Renderiza el grid con el snapshot del motor.
        - Actualiza el panel de estadísticas.
        - Muestra los nuevos eventos en el log.
        """
        snapshot = self.engine.get_snapshot()

        # Renderizar grid
        self.grid_canvas.render(snapshot["grid"])

        # Actualizar estadísticas
        antidote_pct = snapshot.get("antidote_pct", 0)
        antidote_str = (
            "¡LISTO!" if antidote_pct >= 100
            else f"{antidote_pct}%"
        )
        self.stats_panel.update({
            "n_humans": snapshot["n_humans"],
            "n_zombies": snapshot["n_zombies"],
            "infected": snapshot.get("infected", 0),
            "tick": snapshot["tick"],
            "strategy": snapshot["strategy"],
            "antidote": antidote_str,
            "result": snapshot["result"] or "En curso",
        })

        # Mostrar eventos nuevos
        events = self.engine.world.pop_events()
        for event in events:
            self.event_log.add_event(event["description"])

    # ------------------------------------------------------------------
    # Acciones de control (llamadas desde ControlPanel)
    # ------------------------------------------------------------------

    def action_start(self) -> None:
        """Inicia la simulación si no está en marcha."""
        if not self.engine.running:
            self.engine.start_simulation()
            self.event_log.add_event("▶️ Simulación iniciada")

    def action_pause(self) -> None:
        """Pausa o reanuda la simulación."""
        self.engine.pause()
        state = "⏸ Pausada" if self.engine.paused else "▶️ Reanudada"
        self.event_log.add_event(state)

    def action_reset(self) -> None:
        """Reinicia la simulación."""
        self.engine.reset()
        self.grid_canvas.clear()
        self.event_log.add_event("🔄 Simulación reiniciada")

    def action_run_batch(self, n: int = 100) -> None:
        """
        Ejecuta n simulaciones en modo batch (sin UI intermedia).

        Los resultados se guardan en la base de datos.

        Args:
            n: Número de simulaciones a ejecutar.
        """
        from db.database import Database
        from db.stats import print_summary
        import threading

        def _batch():
            from simulation.engine import Engine
            db = Database()
            self.event_log.add_event(f"🔁 Iniciando batch de {n} simulaciones...")
            for i in range(n):
                eng = Engine()
                eng.start_simulation()
                # Esperar a que termine
                import time
                timeout = 60  # segundos máximo por simulación
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
                    self.event_log.add_event(f"  Completadas {i+1}/{n} simulaciones")
            print_summary(db)
            self.event_log.add_event(f"✅ Batch completado. Ver consola para resumen.")

        t = threading.Thread(target=_batch, daemon=True)
        t.start()
