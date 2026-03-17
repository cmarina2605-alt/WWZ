"""
control_panel.py — Panel de controles de la simulación.

Proporciona al usuario los controles interactivos para manejar la
simulación sin tener que editar código ni reiniciar el programa.

Botones:
    ▶ Start      — arranca la simulación (deshabilitado mientras corre).
    ⏸ Pause      — pausa / reanuda; el texto cambia a "Resume" cuando pausado.
    🔄 Reset      — detiene y reinicia todo desde cero.
    ⚙ Batch×100  — lanza 100 simulaciones headless en background y guarda
                   resultados en la DB para análisis posterior.

Sliders (ajuste en tiempo real):
    Velocidad     — modifica config.TICK_SPEED (0.01 – 0.5 s/tick).
    P(infección)  — modifica config.P_INFECT y engine.p_infect (0.0 – 1.0).
    N. Humanos    — modifica config.NUM_HUMANS para la próxima simulación.
    Visión Zombi  — modifica config.VISION_ZOMBIE (5 – 30 celdas).

Nota: los cambios de Velocidad, P(infección) y Visión Zombi tienen efecto
inmediato. N. Humanos solo aplica al hacer Reset + Start.
"""

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from ui.app import App


class ControlPanel(tk.Frame):
    """
    Panel de control con botones y sliders interactivos.

    Permite al usuario iniciar, pausar y reiniciar la simulación,
    así como ajustar parámetros en tiempo real mediante sliders.

    Sliders disponibles:
        - Velocidad de simulación (tick_speed).
        - Probabilidad de infección (p_infect).
        - Número de humanos (n_humans).
        - Visión de los zombis (vision_zombie).

    Attributes:
        app (App): Referencia a la ventana principal.
    """

    def __init__(self, parent: tk.Widget, app: "App") -> None:
        """
        Inicializa el panel de control.

        Args:
            parent: Widget padre.
            app: Referencia a la App principal para llamar acciones.
        """
        super().__init__(parent, bg="#16213e", padx=5, pady=5)
        self.app: "App" = app
        self._build_buttons()
        self._build_sliders()

    # ------------------------------------------------------------------
    # Construcción de botones
    # ------------------------------------------------------------------

    def _build_buttons(self) -> None:
        """Construye la fila de botones de control."""
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
    # Construcción de sliders
    # ------------------------------------------------------------------

    def _build_sliders(self) -> None:
        """Construye los sliders de ajuste de parámetros."""
        slider_frame = tk.Frame(self, bg="#16213e")
        slider_frame.pack(fill=tk.X)

        self._sliders: dict = {}

        slider_defs = [
            {
                "label": "Velocidad",
                "key": "tick_speed",
                "from_": 0.01,
                "to": 0.5,
                "resolution": 0.01,
                "default": config.TICK_SPEED,
                "callback": self._on_speed_change,
            },
            {
                "label": "P(infección)",
                "key": "p_infect",
                "from_": 0.0,
                "to": 1.0,
                "resolution": 0.05,
                "default": config.P_INFECT,
                "callback": self._on_p_infect_change,
            },
            {
                "label": "N. Humanos",
                "key": "n_humans",
                "from_": 10,
                "to": 300,
                "resolution": 10,
                "default": config.NUM_HUMANS,
                "callback": self._on_n_humans_change,
            },
            {
                "label": "Visión Zombi",
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
    # Callbacks de sliders
    # ------------------------------------------------------------------

    def _on_speed_change(self, value: str) -> None:
        """
        Actualiza la velocidad global de la simulación.

        Args:
            value: Nuevo valor del slider como string.
        """
        config.TICK_SPEED = float(value)

    def _on_p_infect_change(self, value: str) -> None:
        """
        Actualiza la probabilidad de infección en tiempo real.

        Args:
            value: Nuevo valor (0.0 - 1.0).
        """
        config.P_INFECT = float(value)
        self.app.engine.p_infect = float(value)

    def _on_n_humans_change(self, value: str) -> None:
        """
        Actualiza el número de humanos para la próxima simulación.

        Nota: Solo tiene efecto al hacer Reset + Start.

        Args:
            value: Nuevo valor (10 - 300).
        """
        config.NUM_HUMANS = int(float(value))

    def _on_vision_zombie_change(self, value: str) -> None:
        """
        Actualiza el rango de visión de los zombis en tiempo real.

        Args:
            value: Nuevo valor en celdas.
        """
        config.VISION_ZOMBIE = int(float(value))

    # ------------------------------------------------------------------
    # Estado de los botones
    # ------------------------------------------------------------------

    def set_button_state(self, running: bool, paused: bool) -> None:
        """
        Actualiza el estado visual de los botones según la simulación.

        Args:
            running: True si la simulación está en marcha.
            paused: True si está pausada.
        """
        if running and not paused:
            self.btn_start.config(state=tk.DISABLED)
            self.btn_pause.config(text="⏸ Pause")
        elif running and paused:
            self.btn_pause.config(text="▶ Resume")
        else:
            self.btn_start.config(state=tk.NORMAL)
            self.btn_pause.config(text="⏸ Pause")
