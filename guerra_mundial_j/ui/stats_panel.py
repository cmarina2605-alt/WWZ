"""
stats_panel.py — Real-time statistics panel.

Displays key simulation indicators in real time,
refreshing every UI_REFRESH_MS milliseconds from app.py.

Statistics shown:
    🧍 Humans    — number of living humans (green).
    🧟 Zombies   — number of active zombies (yellow).
    🟠 Infected  — humans in incubation period (orange).
    ⏱  Tick      — global simulation tick (light blue).
    ⚙  Protocol  — active human strategy: flee/group/military_first/random.
    💉 Antidote  — progress of the most advanced scientist in the lab (0%–READY!).
    🏁 Status    — result: "In progress", "humans_win" or "zombies_win".

Implementation:
    Each row is a pair (static Label, Label with tk.StringVar).
    update(stats_dict) updates the StringVars with the received values.
    reset() sets all values to "—" (used after simulation Reset).
"""

import tkinter as tk
from typing import Dict, Any


class StatsPanel(tk.Frame):
    """
    Real-time simulation statistics panel.

    Displays labels that update with each call to update().

    Statistics shown:
        - Living humans
        - Active zombies
        - Infected
        - Current tick
        - Active strategy
        - Result (if simulation ended)

    Attributes:
        _vars (Dict[str, tk.StringVar]): Tkinter variables bound
            to each value label.
    """

    STAT_DEFS = [
        ("n_humans",  "🧍 Humans",    "#00ff88"),
        ("n_zombies", "🧟 Zombies",   "#ffff00"),
        ("infected",  "🟠 Infected",  "#ffa500"),
        ("tick",      "⏱  Tick",      "#87ceeb"),
        ("phase",     "📍 Phase",     "#ff9944"),
        ("strategy",  "⚙  Protocol", "#da70d6"),
        ("antidote",  "💉 Antidote",  "#00cfff"),
        ("result",    "🏁 Status",    "#ffffff"),
    ]

    def __init__(self, parent: tk.Widget) -> None:
        """
        Initializes the statistics panel.

        Args:
            parent: Tkinter parent widget.
        """
        super().__init__(parent, bg="#16213e", padx=5, pady=5)
        self._vars: Dict[str, tk.StringVar] = {}
        self._build_layout()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        """Builds the statistics label rows."""
        title = tk.Label(
            self,
            text="📊 STATISTICS",
            bg="#16213e",
            fg="#58a6ff",
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        for i, (key, label, color) in enumerate(self.STAT_DEFS, start=1):
            # Field label
            tk.Label(
                self,
                text=f"{label}:",
                bg="#16213e",
                fg="#888888",
                font=("Consolas", 9),
                anchor="w",
                width=16,
            ).grid(row=i, column=0, sticky="w", pady=1)

            # Value variable and label
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
    # Public API
    # ------------------------------------------------------------------

    def update(self, stats: Dict[str, Any]) -> None:
        """
        Refreshes all panel values.

        Accepts a dict with any subset of keys defined in STAT_DEFS;
        missing keys are not modified.

        Args:
            stats: Dict with updated values. Expected keys:
                   n_humans, n_zombies, infected, tick, strategy, result.

        Example:
            >>> panel.update({
            ...     "n_humans": 87,
            ...     "n_zombies": 14,
            ...     "tick": 342,
            ...     "strategy": "flee",
            ...     "result": "In progress",
            ... })
        """
        for key, var in self._vars.items():
            if key in stats:
                value = stats[key]
                var.set(str(value) if value is not None else "—")

    def reset(self) -> None:
        """Resets all values to "—"."""
        for var in self._vars.values():
            var.set("—")
