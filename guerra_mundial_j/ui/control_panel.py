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
        super().__init__(parent, bg="#0d1117", padx=6, pady=6)
        self.app: "App" = app
        self._build_buttons()
        self._build_sliders()

    # ------------------------------------------------------------------
    # Button construction
    # ------------------------------------------------------------------

    def _build_buttons(self) -> None:
        """Builds the control button row."""
        # Title
        tk.Label(
            self, text="⚙ CONTROLS",
            bg="#0d1117", fg="#58a6ff",
            font=("Consolas", 9, "bold"), anchor="w",
        ).pack(fill=tk.X, pady=(0, 5))

        btn_frame = tk.Frame(self, bg="#0d1117")
        btn_frame.pack(fill=tk.X, pady=(0, 6))

        btn_style = {
            "font": ("Consolas", 10, "bold"),
            "relief": tk.FLAT,
            "padx": 10,
            "pady": 5,
            "cursor": "hand2",
            "activeforeground": "white",
            "bd": 0,
        }

        self.btn_start = tk.Button(
            btn_frame, text="▶  Start",
            bg="#0d4a28", fg="#40c870",
            activebackground="#1a6a3a",
            command=self.app.action_start,
            **btn_style,
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 3))

        self.btn_pause = tk.Button(
            btn_frame, text="⏸  Pause",
            bg="#2a1a4a", fg="#c084fc",
            activebackground="#3a2a6a",
            command=self.app.action_pause,
            **btn_style,
        )
        self.btn_pause.pack(side=tk.LEFT, padx=3)

        self.btn_reset = tk.Button(
            btn_frame, text="↺  Reset",
            bg="#4a0d1a", fg="#e05252",
            activebackground="#6a1a28",
            command=self.app.action_reset,
            **btn_style,
        )
        self.btn_reset.pack(side=tk.LEFT, padx=3)

        self.btn_batch = tk.Button(
            btn_frame, text="⚙ Batch×100",
            bg="#1a2a1a", fg="#888888",
            activebackground="#263426",
            command=lambda: self.app.action_run_batch(100),
            **btn_style,
        )
        self.btn_batch.pack(side=tk.LEFT, padx=3)

    # ------------------------------------------------------------------
    # Slider construction
    # ------------------------------------------------------------------

    def _build_sliders(self) -> None:
        """Builds the parameter adjustment sliders."""
        tk.Label(
            self, text="Adjust parameters (live):",
            bg="#0d1117", fg="#555555",
            font=("Consolas", 7), anchor="w",
        ).pack(fill=tk.X, pady=(0, 2))

        slider_frame = tk.Frame(self, bg="#0d1117")
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
            row = tk.Frame(slider_frame, bg="#0d1117")
            row.pack(fill=tk.X, pady=1)

            tk.Label(
                row, text=f"{sd['label']:<14}",
                bg="#0d1117", fg="#aaaaaa",
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
                length=190,
                bg="#0d1117", fg="#aaaaaa",
                troughcolor="#1a2a4a",
                activebackground="#4e9eff",
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
        config.TICK_SPEED = 0.51 - float(value)

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
            self.btn_start.config(state=tk.DISABLED, fg="#555555")
            self.btn_pause.config(text="⏸  Pause", fg="#c084fc")
        elif running and paused:
            self.btn_pause.config(text="▶  Resume", fg="#40c870")
        else:
            self.btn_start.config(state=tk.NORMAL, fg="#40c870")
            self.btn_pause.config(text="⏸  Pause", fg="#c084fc")
