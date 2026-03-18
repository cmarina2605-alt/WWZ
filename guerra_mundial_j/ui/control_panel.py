"""
control_panel.py — Simulation controls panel.

Provides the user with interactive controls to manage the simulation
without editing code or restarting the program.

Buttons:
    ▶ Start      — starts the simulation (disabled while running).
    ⏸ Pause      — pauses / resumes; text changes to "Resume" when paused.
    🔄 Reset      — stops and restarts everything from scratch.
    ⚙ Batch×100  — launches 100 headless simulations in the background and
                   saves results to the DB for later analysis.

Sliders (real-time adjustment):
    Speed         — modifies config.TICK_SPEED (0.01 – 0.5 s/tick).
    P(infection)  — modifies config.P_INFECT and engine.p_infect (0.0 – 1.0).
    N. Humans     — modifies config.NUM_HUMANS for the next simulation.
    Zombie Vision — modifies config.VISION_ZOMBIE (5 – 30 cells).

Note: Speed, P(infection) and Zombie Vision changes take effect immediately.
N. Humans only applies after Reset + Start.
"""

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from ui.app import App


class ControlPanel(tk.Frame):
    """
    Control panel with interactive buttons and sliders.

    Allows the user to start, pause, and reset the simulation,
    as well as adjust parameters in real time via sliders.

    Available sliders:
        - Simulation speed (tick_speed).
        - Infection probability (p_infect).
        - Number of humans (n_humans).
        - Zombie vision (vision_zombie).

    Attributes:
        app (App): Reference to the main window.
    """

    def __init__(self, parent: tk.Widget, app: "App") -> None:
        """
        Initializes the control panel.

        Args:
            parent: Parent widget.
            app: Reference to the main App for calling actions.
        """
        super().__init__(parent, bg="#16213e", padx=5, pady=5)
        self.app: "App" = app
        self._build_buttons()
        self._build_sliders()

    # ------------------------------------------------------------------
    # Button construction
    # ------------------------------------------------------------------

    def _build_buttons(self) -> None:
        """Builds the control button row."""
        btn_frame = tk.Frame(self, bg="#16213e")
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        btn_style = {
            "font": ("Consolas", 10, "bold"),
            "relief": tk.FLAT,
            "padx": 8,
            "pady": 4,
            "cursor": "hand2",
        }

        self.btn_start = tk.Button(
            btn_frame, text="▶ Start",
            bg="#0f3460", fg="white",
            command=self.app.action_start,
            **btn_style,
        )
        self.btn_start.pack(side=tk.LEFT, padx=2)

        self.btn_pause = tk.Button(
            btn_frame, text="⏸ Pause",
            bg="#533483", fg="white",
            command=self.app.action_pause,
            **btn_style,
        )
        self.btn_pause.pack(side=tk.LEFT, padx=2)

        self.btn_reset = tk.Button(
            btn_frame, text="🔄 Reset",
            bg="#e94560", fg="white",
            command=self.app.action_reset,
            **btn_style,
        )
        self.btn_reset.pack(side=tk.LEFT, padx=2)

        self.btn_batch = tk.Button(
            btn_frame, text="⚙ Batch×100",
            bg="#1a472a", fg="white",
            command=lambda: self.app.action_run_batch(100),
            **btn_style,
        )
        self.btn_batch.pack(side=tk.LEFT, padx=2)

    # ------------------------------------------------------------------
    # Slider construction
    # ------------------------------------------------------------------

    def _build_sliders(self) -> None:
        """Builds the parameter adjustment sliders."""
        slider_frame = tk.Frame(self, bg="#16213e")
        slider_frame.pack(fill=tk.X)

        self._sliders: dict = {}

        slider_defs = [
            {
                "label": "Speed",
                "key": "tick_speed",
                "from_": 0.01,
                "to": 0.5,
                "resolution": 0.01,
                "default": config.TICK_SPEED,
                "callback": self._on_speed_change,
            },
            {
                "label": "P(infection)",
                "key": "p_infect",
                "from_": 0.0,
                "to": 1.0,
                "resolution": 0.05,
                "default": config.P_INFECT,
                "callback": self._on_p_infect_change,
            },
            {
                "label": "N. Humans",
                "key": "n_humans",
                "from_": 10,
                "to": 300,
                "resolution": 10,
                "default": config.NUM_HUMANS,
                "callback": self._on_n_humans_change,
            },
            {
                "label": "Zombie Vision",
                "key": "vision_zombie",
                "from_": 5,
                "to": 30,
                "resolution": 1,
                "default": config.VISION_ZOMBIE,
                "callback": self._on_vision_zombie_change,
            },
        ]

        for sd in slider_defs:
            row = tk.Frame(slider_frame, bg="#16213e")
            row.pack(fill=tk.X, pady=1)

            tk.Label(
                row, text=f"{sd['label']:<14}",
                bg="#16213e", fg="#aaaaaa",
                font=("Consolas", 9),
                width=14, anchor="w",
            ).pack(side=tk.LEFT)

            var = tk.DoubleVar(value=sd["default"])
            slider = tk.Scale(
                row,
                variable=var,
                from_=sd["from_"],
                to=sd["to"],
                resolution=sd["resolution"],
                orient=tk.HORIZONTAL,
                length=180,
                bg="#16213e", fg="white",
                troughcolor="#0f3460",
                highlightthickness=0,
                command=sd["callback"],
                showvalue=True,
                font=("Consolas", 8),
            )
            slider.pack(side=tk.LEFT, padx=4)
            self._sliders[sd["key"]] = (slider, var)

    # ------------------------------------------------------------------
    # Slider callbacks
    # ------------------------------------------------------------------

    def _on_speed_change(self, value: str) -> None:
        """
        Updates the global simulation speed.

        Args:
            value: New slider value as string.
        """
        config.TICK_SPEED = float(value)

    def _on_p_infect_change(self, value: str) -> None:
        """
        Updates the infection probability in real time.

        Args:
            value: New value (0.0 - 1.0).
        """
        config.P_INFECT = float(value)
        self.app.engine.p_infect = float(value)

    def _on_n_humans_change(self, value: str) -> None:
        """
        Updates the number of humans for the next simulation.

        Note: Only takes effect after Reset + Start.

        Args:
            value: New value (10 - 300).
        """
        config.NUM_HUMANS = int(float(value))

    def _on_vision_zombie_change(self, value: str) -> None:
        """
        Updates the zombie vision range in real time.

        Args:
            value: New value in cells.
        """
        config.VISION_ZOMBIE = int(float(value))

    # ------------------------------------------------------------------
    # Button state
    # ------------------------------------------------------------------

    def set_button_state(self, running: bool, paused: bool) -> None:
        """
        Updates the visual state of buttons based on simulation state.

        Args:
            running: True if simulation is running.
            paused: True if paused.
        """
        if running and not paused:
            self.btn_start.config(state=tk.DISABLED)
            self.btn_pause.config(text="⏸ Pause")
        elif running and paused:
            self.btn_pause.config(text="▶ Resume")
        else:
            self.btn_start.config(state=tk.NORMAL)
            self.btn_pause.config(text="⏸ Pause")
