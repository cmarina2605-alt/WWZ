"""
grid_canvas.py — Tkinter Canvas that draws the U.S. map for the simulation.

GridCanvas renders the world state on an approximate geographic map of the
continental United States. The map is drawn once at startup (ocean, land,
states, key cities) and agents are overlaid frame by frame as colored
circles — one distinct color per agent role.

Rendering layers (bottom to top):
    1. Ocean background (bg OCEAN_COLOR).
    2. Continental U.S. polygon (LAND_COLOR).
    3. State division lines (STATE_LINE_COLOR, dashed).
    4. Key city markers (San Diego, Washington D.C., Atlanta, Fort Bragg).
    5. Agent color legend (bottom-left corner).
    6. Agent circles — updated each frame, big enough to be distinguishable.

Optimization:
    - Uses a PRE-ALLOCATED POOL of canvas oval items.
    - Each frame only calls coords() and itemconfig() — no create/delete.
    - This eliminates the Python→Tcl overhead of creating and destroying
      hundreds of canvas items every 80ms.
"""

import tkinter as tk
from typing import Dict, Tuple, Any, Optional

import config


class GridCanvas(tk.Canvas):
    """
    Canvas that visualizes the agent grid on a U.S. map using colored circles.

    Uses a pre-allocated pool of canvas ovals that are repositioned each
    frame instead of being deleted and recreated. This is dramatically
    faster for Tkinter's canvas implementation.

    Attributes:
        canvas_size (int): Canvas size in pixels (square).
        cell_size (float): Size in pixels of each grid cell.
        _pool (list): Pre-allocated canvas oval item IDs.
        _pool_colors (list): Current fill color of each pool item (for diff).
        _active (int): Number of pool items currently visible.
    """

    # ------------------------------------------------------------------
    # Map color constants
    # ------------------------------------------------------------------
    OCEAN_COLOR       = config.OCEAN_COLOR
    LAND_COLOR        = config.LAND_COLOR
    LAND_BORDER_COLOR = config.LAND_BORDER_COLOR
    STATE_LINE_COLOR  = config.STATE_LINE_COLOR

    # ------------------------------------------------------------------
    # Map geometry
    # ------------------------------------------------------------------

    USA_POLYGON = config.USA_POLYGON

    # Approximate state division lines (dashed strokes) — scaled to 250×250
    STATE_REGION_LINES = [
        [(38, 8), (36, 30), (35, 60), (35, 100), (35, 140), (35, 180), (35, 195)],
        [(70, 5), (68, 30), (67, 60), (67, 100), (67, 140), (68, 180), (72, 210)],
        [(108, 5), (106, 30), (105, 60), (105, 100), (106, 140), (108, 180), (108, 210)],
        [(165, 8), (168, 30), (170, 60), (172, 80), (175, 100), (180, 120), (185, 140)],
        [(35, 140), (70, 142), (108, 145), (140, 148), (170, 150), (200, 140)],
        [(35, 60), (70, 58), (108, 56), (140, 55), (165, 54)],
    ]

    # Key cities / zones
    CITY_MARKERS = [
        ("OUTBREAK_POS",      "San Diego",       "Outbreak",      "#ff4444"),
        ("WHITEHOUSE_POS",    "Washington D.C.", "White House",   "#ffffff"),
        ("LAB_POS",           "Atlanta, GA",     "CDC",           "#00cfff"),
        ("MILITARY_BASE_POS", "Fort Bragg, NC",  "Military Base", "#00ff88"),
    ]

    # Color mapping: role → (fill_color, outline_color)
    ROLE_COLORS: Dict[str, Tuple[str, str]] = {
        "normal":     (config.COLOR_NORMAL,     "#5a7a90"),
        "military":   (config.COLOR_MILITARY,   "#a08830"),
        "scientist":  (config.COLOR_SCIENTIST,  "#cccccc"),
        "politician": (config.COLOR_POLITICIAN, "#9050b0"),
        "president":  (config.COLOR_PRESIDENT,  "#cc9900"),
        "zombie":     (config.COLOR_ZOMBIE,     "#00cc33"),
        "infected":   (config.COLOR_INFECTED,   "#cc4400"),
        "dead":       (config.COLOR_DEAD,       "#1a1a1a"),
    }

    # Legend entries: (label, role_key)
    LEGEND_ENTRIES = [
        ("Normal",     "normal"),
        ("Military",   "military"),
        ("Scientist",  "scientist"),
        ("Politician", "politician"),
        ("President",  "president"),
        ("Zombie",     "zombie"),
        ("Infected",   "infected"),
    ]

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(self, parent: tk.Widget, size: int = config.CANVAS_SIZE) -> None:
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=self.OCEAN_COLOR,
            highlightthickness=0,
        )
        self.canvas_size: int = size
        self.cell_size: float = size / config.GRID_SIZE

        # Agent circle radii
        self._dot_radius: float = max(2.0, self.cell_size * 1.0)
        self._zombie_radius: float = max(3.0, self.cell_size * 1.6)

        # Pre-allocated pool of canvas items (avoids create/delete per frame)
        self._pool: list = []
        self._pool_colors: list = []   # track current fill to skip no-ops
        self._active: int = 0          # how many pool items are currently visible

        # Draw static map layers
        self._draw_usa_background()
        self._draw_zones()
        self._draw_legend()

    # ------------------------------------------------------------------
    # Static map drawing
    # ------------------------------------------------------------------

    def _draw_usa_background(self) -> None:
        """Draws the continental U.S. polygon with state division lines."""
        cs = self.cell_size

        pts = []
        for gx, gy in self.USA_POLYGON:
            pts.extend([gx * cs, gy * cs])
        self.create_polygon(
            pts,
            fill=self.LAND_COLOR,
            outline=self.LAND_BORDER_COLOR,
            width=1.5,
        )

        # Draw approximate state division lines for visual context
        for line in self.STATE_REGION_LINES:
            pts = []
            for gx, gy in line:
                pts.extend([gx * cs, gy * cs])
            if len(pts) >= 4:
                self.create_line(
                    pts,
                    fill=self.STATE_LINE_COLOR,
                    width=0.8,
                    dash=(4, 6),
                    smooth=True,
                )

    def _draw_zones(self) -> None:
        """Draws key city markers with name and label."""
        cs = self.cell_size
        r = max(8, config.LAB_RADIUS * cs)

        for attr, line1, line2, color in self.CITY_MARKERS:
            gx, gy = getattr(config, attr)
            px, py = gx * cs, gy * cs

            self.create_oval(
                px - r - 3, py - r - 3, px + r + 3, py + r + 3,
                outline=color, fill="", width=0.5, dash=(2, 4),
            )
            self.create_oval(
                px - r, py - r, px + r, py + r,
                outline=color, fill="", width=1.5, dash=(3, 3),
            )
            self.create_oval(
                px - 3, py - 3, px + 3, py + 3,
                fill=color, outline="#000000", width=1,
            )
            self.create_text(
                px, py - r - 12,
                text=line1, fill=color,
                font=("Consolas", 8, "bold"),
            )
            self.create_text(
                px, py - r - 2,
                text=line2, fill=color,
                font=("Consolas", 7),
            )

    def _draw_legend(self) -> None:
        """Draws the agent type legend in the bottom-left corner using colored circles."""
        cs = self.cell_size
        x0 = int(10 * cs)
        y0 = int(210 * cs)
        dot_r = 5
        row_h = 18
        pad = 6

        total_h = len(self.LEGEND_ENTRIES) * row_h + pad * 2

        self.create_rectangle(
            x0 - pad, y0 - pad,
            x0 + 100, y0 + total_h - pad,
            fill="#000000", outline="#333333", width=1, stipple="gray50",
        )

        y = y0
        for label, role_key in self.LEGEND_ENTRIES:
            fill, outline = self.ROLE_COLORS.get(role_key, ("#888888", "#666666"))
            cy = y + dot_r + 2
            self.create_oval(
                x0, cy - dot_r,
                x0 + dot_r * 2, cy + dot_r,
                fill=fill, outline=outline, width=1,
            )
            self.create_text(
                x0 + dot_r * 2 + 6, cy,
                text=label, anchor="w",
                fill="#dddddd", font=("Consolas", 8),
            )
            y += row_h

    # ------------------------------------------------------------------
    # Pool management
    # ------------------------------------------------------------------

    def _ensure_pool(self, n: int) -> None:
        """
        Grows the pool to at least n items if needed.

        New items are created hidden and off-screen. They will be
        positioned and shown by render().
        """
        while len(self._pool) < n:
            item_id = self.create_oval(
                -10, -10, -10, -10,
                fill="", outline="", width=1,
                state="hidden",
                tags="agent",
            )
            self._pool.append(item_id)
            self._pool_colors.append("")

    # ------------------------------------------------------------------
    # Agent rendering (frame by frame) — pool-based colored circles
    # ------------------------------------------------------------------

    def _resolve_role_key(
        self,
        agent_type: str,
        role: str,
        state: str,
        is_president: bool = False,
    ) -> str:
        """
        Determines which color role key to use for a given agent.

        Priority order:
            1. Dead agents → "dead"
            2. Infected humans → "infected"
            3. Zombies → "zombie"
            4. President → "president"
            5. Role-specific (military, scientist, politician)
            6. Fallback → "normal"
        """
        if state == "dead":
            return "dead"
        if state == "infected" and agent_type != "Zombie":
            return "infected"
        if agent_type == "Zombie":
            return "zombie"
        if is_president or role == "president":
            return "president"
        if role in ("military", "scientist", "politician"):
            return role
        return "normal"

    def render(
        self,
        snapshot: Dict[Tuple[int, int], Dict[str, str]],
    ) -> None:
        """
        Updates visible agents from the Engine snapshot using a pre-allocated
        pool of canvas ovals.

        Instead of deleting and creating canvas items every frame (slow),
        this method repositions existing items with coords() and only
        calls itemconfig() when the color changes. Hidden items are
        parked off-screen.

        Args:
            snapshot: Dict of {(x, y): {"type", "role", "state", ...}} from World.
        """
        items = list(snapshot.items())
        n = len(items)
        self._ensure_pool(n)

        cs = self.cell_size
        r_default = self._dot_radius
        r_zombie = self._zombie_radius

        for i, (pos, agent_data) in enumerate(items):
            item_id = self._pool[i]

            role_key = self._resolve_role_key(
                agent_data.get("type", ""),
                agent_data.get("role", ""),
                agent_data.get("state", ""),
                agent_data.get("is_president", False),
            )

            # Zombies get a bigger circle so they stand out
            r = r_zombie if role_key == "zombie" else r_default

            # Reposition the circle
            px = pos[0] * cs + cs / 2
            py = pos[1] * cs + cs / 2
            self.coords(item_id, px - r, py - r, px + r, py + r)

            # Only update color if it changed (itemconfig is expensive)
            if self._pool_colors[i] != role_key:
                fill, outline = self.ROLE_COLORS.get(role_key, ("#888888", "#666666"))
                self.itemconfig(item_id, fill=fill, outline=outline, state="normal")
                self._pool_colors[i] = role_key
            elif i >= self._active:
                # Item was hidden, make it visible
                self.itemconfig(item_id, state="normal")

        # Hide any pool items beyond what we need
        for i in range(n, self._active):
            self.itemconfig(self._pool[i], state="hidden")
            self._pool_colors[i] = ""

        self._active = n

    def clear(self) -> None:
        """Hides all agent circles (without touching the base map)."""
        for i in range(self._active):
            self.itemconfig(self._pool[i], state="hidden")
            self._pool_colors[i] = ""
        self._active = 0

    # ------------------------------------------------------------------
    # Game over overlay
    # ------------------------------------------------------------------

    def show_game_over(self, result: str) -> None:
        """
        Draws a dramatic overlay announcing the simulation result.

        Args:
            result: "humans_win" or "zombies_win".
        """
        self.delete("overlay")
        w = self.canvas_size
        h = self.canvas_size

        if result == "humans_win":
            bg     = "#001833"
            title  = "HUMANITY SURVIVES!"
            sub    = "The antidote has been found"
            color  = "#00ff88"
        else:
            bg     = "#1a0000"
            title  = "ZOMBIES WIN!"
            sub    = "The infection has consumed the nation"
            color  = "#ff4444"

        self.create_rectangle(
            0, 0, w, h,
            fill=bg, outline="", stipple="gray75",
            tags="overlay",
        )
        self.create_rectangle(
            w // 4, h // 2 - 60, 3 * w // 4, h // 2 + 60,
            fill="#000000", outline=color, width=2, stipple="gray50",
            tags="overlay",
        )
        self.create_text(
            w // 2, h // 2 - 18,
            text=title,
            fill=color,
            font=("Consolas", 20, "bold"),
            tags="overlay",
        )
        self.create_text(
            w // 2, h // 2 + 18,
            text=sub,
            fill="#aaaaaa",
            font=("Consolas", 10),
            tags="overlay",
        )

    def clear_overlay(self) -> None:
        """Removes the game-over overlay."""
        self.delete("overlay")
