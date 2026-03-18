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

import config


class StatsPanel(tk.Frame):
    """
    Real-time simulation statistics panel.

    Shows a population ratio bar (humans / infected / zombies),
    an antidote progress bar, and key text statistics.

    Attributes:
        _vars (Dict[str, tk.StringVar]): Tkinter variables bound
            to each value label.
    """

    # Stats shown as text rows (key, label, color)
    STAT_DEFS = [
        ("tick",      "⏱  Tick",      "#87ceeb"),
        ("phase",     "📍 Phase",     "#ff9944"),
        ("strategy",  "⚙  Protocol", "#da70d6"),
        ("result",    "🏁 Status",    "#ffffff"),
    ]

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, bg="#16213e", padx=6, pady=6)
        self._vars: Dict[str, tk.StringVar] = {}
        self._n_humans = 0
        self._n_zombies = 0
        self._infected = 0
        self._antidote_pct = 0
        self._build_layout()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        """Builds the full statistics panel."""
        # Title
        tk.Label(
            self, text="📊 STATISTICS",
            bg="#16213e", fg="#58a6ff",
            font=("Consolas", 9, "bold"), anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))

        # ── Population counters row ──────────────────────────────────
        counts_row = tk.Frame(self, bg="#16213e")
        counts_row.pack(fill=tk.X, pady=(0, 3))

        self._lbl_humans = self._big_counter(counts_row, "0", config.COLOR_MILITARY, "🧍 Humans")
        self._lbl_humans.pack(side=tk.LEFT, expand=True)

        tk.Frame(counts_row, bg="#2a3a5a", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=4)

        self._lbl_infected = self._big_counter(counts_row, "0", config.COLOR_INFECTED, "🟠 Infected")
        self._lbl_infected.pack(side=tk.LEFT, expand=True)

        tk.Frame(counts_row, bg="#2a3a5a", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=4)

        self._lbl_zombies = self._big_counter(counts_row, "0", config.COLOR_ZOMBIE, "🧟 Zombies")
        self._lbl_zombies.pack(side=tk.LEFT, expand=True)

        # ── Population ratio bar ─────────────────────────────────────
        tk.Label(
            self, text="Population balance:",
            bg="#16213e", fg="#555555",
            font=("Consolas", 7), anchor="w",
        ).pack(fill=tk.X)

        self._pop_bar = tk.Canvas(
            self, height=12, bg="#0a0a1a",
            highlightthickness=1, highlightbackground="#1e2a4a",
        )
        self._pop_bar.pack(fill=tk.X, pady=(0, 5))

        # ── Antidote progress bar ────────────────────────────────────
        antidote_row = tk.Frame(self, bg="#16213e")
        antidote_row.pack(fill=tk.X, pady=(0, 3))

        tk.Label(
            antidote_row, text="💉 Antidote:",
            bg="#16213e", fg="#888888",
            font=("Consolas", 9), anchor="w", width=14,
        ).pack(side=tk.LEFT)

        self._antidote_var = tk.StringVar(value="—")
        tk.Label(
            antidote_row, textvariable=self._antidote_var,
            bg="#16213e", fg="#00cfff",
            font=("Consolas", 9, "bold"), anchor="w",
        ).pack(side=tk.LEFT)

        self._antidote_bar = tk.Canvas(
            self, height=8, bg="#0a0a1a",
            highlightthickness=1, highlightbackground="#1e2a4a",
        )
        self._antidote_bar.pack(fill=tk.X, pady=(0, 5))

        # ── Text stat rows ───────────────────────────────────────────
        grid_frame = tk.Frame(self, bg="#16213e")
        grid_frame.pack(fill=tk.X)
        for i, (key, label, color) in enumerate(self.STAT_DEFS):
            tk.Label(
                grid_frame, text=f"{label}:",
                bg="#16213e", fg="#888888",
                font=("Consolas", 9), anchor="w", width=14,
            ).grid(row=i, column=0, sticky="w", pady=1)
            var = tk.StringVar(value="—")
            self._vars[key] = var
            tk.Label(
                grid_frame, textvariable=var,
                bg="#16213e", fg=color,
                font=("Consolas", 9, "bold"), anchor="w",
            ).grid(row=i, column=1, sticky="w", padx=(4, 0))
        grid_frame.columnconfigure(1, weight=1)

    def _big_counter(
        self, parent: tk.Widget, initial: str, color: str, label: str
    ) -> tk.Frame:
        """Creates a large number + small label widget."""
        f = tk.Frame(parent, bg="#16213e")
        self._vars.setdefault(label, tk.StringVar(value=initial))
        num_var = tk.StringVar(value=initial)
        tk.Label(
            f, textvariable=num_var,
            bg="#16213e", fg=color,
            font=("Consolas", 18, "bold"),
        ).pack()
        tk.Label(
            f, text=label,
            bg="#16213e", fg="#555555",
            font=("Consolas", 7),
        ).pack()
        # Store references for update()
        f._num_var = num_var  # type: ignore[attr-defined]
        return f

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, stats: Dict[str, Any]) -> None:
        """
        Refreshes all panel values.

        Args:
            stats: Dict with updated values (n_humans, n_zombies, infected,
                   tick, phase, strategy, antidote, result).
        """
        n_humans  = stats.get("n_humans",  self._n_humans)
        n_zombies = stats.get("n_zombies", self._n_zombies)
        infected  = stats.get("infected",  self._infected)

        self._n_humans  = int(n_humans)  if n_humans  is not None else 0
        self._n_zombies = int(n_zombies) if n_zombies is not None else 0
        self._infected  = int(infected)  if infected  is not None else 0

        # Update big counters
        self._lbl_humans._num_var.set(str(self._n_humans))     # type: ignore[attr-defined]
        self._lbl_infected._num_var.set(str(self._infected))   # type: ignore[attr-defined]
        self._lbl_zombies._num_var.set(str(self._n_zombies))   # type: ignore[attr-defined]

        # Population bar
        self._redraw_pop_bar()

        # Antidote
        antidote_str = stats.get("antidote", "—")
        self._antidote_var.set(str(antidote_str) if antidote_str is not None else "—")
        try:
            pct_str = str(antidote_str).rstrip("%")
            if pct_str == "READY!":
                self._antidote_pct = 100
            else:
                self._antidote_pct = int(pct_str)
        except (ValueError, AttributeError):
            self._antidote_pct = 0
        self._redraw_antidote_bar()

        # Text rows
        for key, var in self._vars.items():
            if key in stats:
                value = stats[key]
                var.set(str(value) if value is not None else "—")

    def reset(self) -> None:
        """Resets all values to "—"."""
        self._n_humans = self._n_zombies = self._infected = self._antidote_pct = 0
        self._lbl_humans._num_var.set("0")    # type: ignore[attr-defined]
        self._lbl_infected._num_var.set("0")  # type: ignore[attr-defined]
        self._lbl_zombies._num_var.set("0")   # type: ignore[attr-defined]
        self._antidote_var.set("—")
        self._pop_bar.delete("all")
        self._antidote_bar.delete("all")
        for var in self._vars.values():
            var.set("—")

    # ------------------------------------------------------------------
    # Bar drawing helpers
    # ------------------------------------------------------------------

    def _redraw_pop_bar(self) -> None:
        """Redraws the population ratio bar."""
        c = self._pop_bar
        c.delete("all")
        w = c.winfo_width()
        if w < 4:
            return
        h = 12
        total = max(1, self._n_humans + self._infected + self._n_zombies)

        x = 0
        segments = [
            (self._n_humans,  config.COLOR_MILITARY),
            (self._infected,  config.COLOR_INFECTED),
            (self._n_zombies, config.COLOR_ZOMBIE),
        ]
        for count, color in segments:
            seg_w = int(count / total * w)
            if seg_w > 0:
                c.create_rectangle(x, 0, x + seg_w, h, fill=color, outline="")
                x += seg_w
        # Fill remainder with dark
        if x < w:
            c.create_rectangle(x, 0, w, h, fill="#1a1a2e", outline="")

    def _redraw_antidote_bar(self) -> None:
        """Redraws the antidote progress bar."""
        c = self._antidote_bar
        c.delete("all")
        w = c.winfo_width()
        if w < 4:
            return
        h = 8
        filled = int(self._antidote_pct / 100 * w)
        if self._antidote_pct >= 100:
            bar_color = "#00ff88"
        else:
            bar_color = "#00cfff"
        c.create_rectangle(0, 0, w, h, fill="#1a1a2e", outline="")
        if filled > 0:
            c.create_rectangle(0, 0, filled, h, fill=bar_color, outline="")
