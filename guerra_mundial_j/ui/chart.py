"""
chart.py — Live population history chart widget.

PopulationChart renders a scrolling line chart showing the count of
humans, zombies, and infected over time. Updated every UI tick.

Rendering:
    - Humans  : green line (COLOR_MILITARY)
    - Zombies : yellow line (COLOR_ZOMBIE)
    - Infected: orange line (COLOR_INFECTED)
    - Faint horizontal grid lines for reference.

Usage:
    chart = PopulationChart(parent)
    chart.pack(fill=tk.X)
    # each UI tick:
    chart.add_point(n_humans, n_zombies, infected)
    # on reset:
    chart.reset()
"""

import tkinter as tk
from typing import List

import config


class PopulationChart(tk.Frame):
    """
    Scrolling line chart of population over time.

    Attributes:
        MAX_POINTS (int): Maximum history length kept in memory.
    """

    MAX_POINTS: int = 300

    def __init__(
        self,
        parent: tk.Widget,
        chart_height: int = 80,
    ) -> None:
        """
        Args:
            parent: Parent widget.
            chart_height: Height of the chart canvas in pixels.
        """
        super().__init__(parent, bg="#0d1117", padx=3, pady=3)
        self._ch = chart_height
        self._humans:  List[int] = []
        self._zombies: List[int] = []
        self._infected: List[int] = []
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Builds the chart canvas and legend."""
        title = tk.Label(
            self,
            text="📈 POPULATION CHART",
            bg="#0d1117",
            fg="#58a6ff",
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        title.pack(fill=tk.X, pady=(0, 2))

        self._canvas = tk.Canvas(
            self,
            height=self._ch,
            bg="#0a0a1a",
            highlightthickness=1,
            highlightbackground="#1e2a4a",
        )
        self._canvas.pack(fill=tk.X)

        # Legend row
        legend = tk.Frame(self, bg="#0d1117")
        legend.pack(fill=tk.X, pady=(3, 0))

        for label, color in [
            ("Humans",   config.COLOR_MILITARY),
            ("Zombies",  config.COLOR_ZOMBIE),
            ("Infected", config.COLOR_INFECTED),
        ]:
            tk.Label(
                legend, text="━", bg="#0d1117", fg=color,
                font=("Consolas", 9, "bold"),
            ).pack(side=tk.LEFT, padx=(6, 1))
            tk.Label(
                legend, text=label, bg="#0d1117", fg="#777777",
                font=("Consolas", 8),
            ).pack(side=tk.LEFT, padx=(0, 8))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_point(self, n_humans: int, n_zombies: int, infected: int = 0) -> None:
        """
        Appends a new data point and redraws the chart.

        Args:
            n_humans: Current living human count.
            n_zombies: Current zombie count.
            infected: Current infected-but-not-yet-zombie count.
        """
        self._humans.append(n_humans)
        self._zombies.append(n_zombies)
        self._infected.append(infected)
        if len(self._humans) > self.MAX_POINTS:
            self._humans.pop(0)
            self._zombies.pop(0)
            self._infected.pop(0)
        self._redraw()

    def reset(self) -> None:
        """Clears all chart data."""
        self._humans.clear()
        self._zombies.clear()
        self._infected.clear()
        self._canvas.delete("all")

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        """Redraws the entire chart."""
        c = self._canvas
        c.delete("all")

        n = len(self._humans)
        if n < 2:
            return

        w = self._canvas.winfo_width()
        h = self._ch
        if w < 10:
            return

        max_val = max(
            max(self._humans,  default=0),
            max(self._zombies, default=0),
            1,
        )

        # Faint horizontal grid lines
        for i in range(1, 5):
            gy = int(4 + (h - 8) * (1 - i / 4))
            c.create_line(2, gy, w - 2, gy, fill="#1a1a3a", width=1)

        def xp(i: int) -> float:
            return 2 + (i / (n - 1)) * (w - 4)

        def yp(v: int) -> float:
            return 4 + (h - 8) * (1.0 - v / max_val)

        # Draw from back to front: infected → zombies → humans
        for series, color in [
            (self._infected, config.COLOR_INFECTED),
            (self._zombies,  config.COLOR_ZOMBIE),
            (self._humans,   config.COLOR_MILITARY),
        ]:
            pts: List[float] = []
            for i, v in enumerate(series):
                pts.extend([xp(i), yp(v)])
            if len(pts) >= 4:
                c.create_line(pts, fill=color, width=1.5, smooth=True)
