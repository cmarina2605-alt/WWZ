"""
stats_panel.py — Panel de estadísticas en tiempo real.

Muestra contadores de humanos, zombis, infectados, tick actual
y estrategia activa, actualizándose cada ciclo de UI.
"""

import tkinter as tk
from typing import Dict, Any


class StatsPanel(tk.Frame):
    """
    Panel de estadísticas de la simulación en tiempo real.

    Muestra etiquetas que se actualizan con cada llamada a update().

    Estadísticas mostradas:
        - Humanos vivos
        - Zombis activos
        - Infectados
        - Tick actual
        - Estrategia activa
        - Resultado (si la simulación terminó)

    Attributes:
        _vars (Dict[str, tk.StringVar]): Variables Tkinter enlazadas
            a cada etiqueta de valor.
    """

    STAT_DEFS = [
        ("n_humans",  "🧍 Humanos",      "#00ff88"),
        ("n_zombies", "🧟 Zombis",        "#ffff00"),
        ("infected",  "🟠 Infectados",    "#ffa500"),
        ("tick",      "⏱  Tick",          "#87ceeb"),
        ("strategy",  "⚙  Estrategia",    "#da70d6"),
        ("antidote",  "💉 Antídoto",      "#00cfff"),
        ("result",    "🏁 Estado",         "#ffffff"),
    ]

    def __init__(self, parent: tk.Widget) -> None:
        """
        Inicializa el panel de estadísticas.

        Args:
            parent: Widget padre de Tkinter.
        """
        super().__init__(parent, bg="#16213e", padx=5, pady=5)
        self._vars: Dict[str, tk.StringVar] = {}
        self._build_layout()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        """Construye las filas de etiquetas de estadísticas."""
        title = tk.Label(
            self,
            text="📊 ESTADÍSTICAS",
            bg="#16213e",
            fg="#58a6ff",
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        for i, (key, label, color) in enumerate(self.STAT_DEFS, start=1):
            # Etiqueta del campo
            tk.Label(
                self,
                text=f"{label}:",
                bg="#16213e",
                fg="#888888",
                font=("Consolas", 9),
                anchor="w",
                width=16,
            ).grid(row=i, column=0, sticky="w", pady=1)

            # Variable y etiqueta de valor
            var = tk.StringVar(value="—")
            self._vars[key] = var
            tk.Label(
                self,
                textvariable=var,
                bg="#16213e",
                fg=color,
                font=("Consolas", 9, "bold"),
                anchor="w",
            ).grid(row=i, column=1, sticky="w", padx=(4, 0))

        self.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def update(self, stats: Dict[str, Any]) -> None:
        """
        Refresca todos los valores del panel.

        Acepta un dict con cualquier subconjunto de las claves
        definidas en STAT_DEFS; las claves ausentes no se modifican.

        Args:
            stats: Dict con los valores actualizados. Claves esperadas:
                   n_humans, n_zombies, infected, tick, strategy, result.

        Example:
            >>> panel.update({
            ...     "n_humans": 87,
            ...     "n_zombies": 14,
            ...     "tick": 342,
            ...     "strategy": "flee",
            ...     "result": "En curso",
            ... })
        """
        for key, var in self._vars.items():
            if key in stats:
                value = stats[key]
                var.set(str(value) if value is not None else "—")

    def reset(self) -> None:
        """Resetea todos los valores a "—"."""
        for var in self._vars.values():
            var.set("—")
