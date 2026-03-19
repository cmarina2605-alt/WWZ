"""
grid_canvas.py — Tkinter Canvas that draws the U.S. map for the simulation.

GridCanvas renders the world state on an approximate geographic map of the
continental United States. The map is drawn once at startup (ocean, land,
states, Great Lakes, key cities) and agents are overlaid frame by frame
as colored rectangles.

Rendering layers (bottom to top):
    1. Ocean background (bg OCEAN_COLOR).
    2. Continental U.S. polygon (LAND_COLOR).
    3. State division lines (STATE_LINE_COLOR, dashed).
    4. Great Lakes (LAKE_COLOR).
    5. Key city markers (San Diego, Washington D.C., Atlanta, Fort Bragg).
    6. Agent color legend (top-left corner).
    7. Agent rectangles — updated each frame without recreating lower layers.

Agent colors:
    Red    — Normal
    Green  — Military
    Purple — Scientist
    Blue   — Politician
    Yellow — Zombie (they're all José!)
    Orange — Infected (incubation)
    Gray   — Dead

Optimization:
    Agent rectangles are reused between frames (itemconfig instead of
    delete+create). When clearing a cell, the rectangle is fully deleted
    so the underlying map remains visible.
"""

import tkinter as tk
from typing import Dict, Tuple, Any

import config


class GridCanvas(tk.Canvas):
    """
    Canvas that visualizes the agent grid on a U.S. map.

    Attributes:
        canvas_size (int): Canvas size in pixels (square).
        cell_size (float): Size in pixels of each grid cell.
        _rect_ids (Dict): Cache of agent rectangle IDs for reuse.
    """

    # ------------------------------------------------------------------
    # Constantes de colores del mapa
    # ------------------------------------------------------------------
    OCEAN_COLOR      = "#0a2040"
    LAND_COLOR       = "#2d5a27"
    LAND_BORDER_COLOR = "#4a8a42"
    STATE_LINE_COLOR = "#3a7a35"
    LAKE_COLOR       = "#1a4a6b"

    # ------------------------------------------------------------------
    # Agent legend  (label, color, shape)
    # ------------------------------------------------------------------
    LEGEND = [
        ("Normal",     config.COLOR_NORMAL,     "circle"),
        ("Military",   config.COLOR_MILITARY,   "square"),
        ("Scientist",  config.COLOR_SCIENTIST,  "circle_outlined"),
        ("Politician", config.COLOR_POLITICIAN, "diamond"),
        ("Zombie",     config.COLOR_ZOMBIE,     "blob"),
        ("Infected",   config.COLOR_INFECTED,   "circle"),
    ]

    # ------------------------------------------------------------------
    # Map geometry
    # ------------------------------------------------------------------

    # Approximate contour of the continental U.S. (shared with simulation layer)
    USA_POLYGON = config.USA_POLYGON

    # Approximate state division lines (dashed strokes)
    STATE_REGION_LINES = [
        # Eastern border of Pacific states (CA / NV-AZ)
        [(15, 3), (14, 20), (14, 40), (14, 60), (14, 78)],
        # Eastern border of Mountain states (CO / Great Plains)
        [(35, 2), (34, 20), (33, 40), (33, 60), (35, 83)],
        # Mississippi River / central divider
        [(56, 2), (55, 20), (55, 40), (55, 60), (54, 85)],
        # Eastern states border
        [(80, 5), (80, 20), (80, 40), (80, 60), (80, 64)],
    ]

    # Great Lakes (cx, cy, rx, ry) in grid coords
    GREAT_LAKES = [
        (58, 17, 8, 4),  # Lake Superior
        (63, 27, 4, 8),  # Lake Michigan
        (70, 23, 6, 5),  # Lake Huron
        (75, 29, 5, 3),  # Lake Erie
        (80, 26, 4, 3),  # Lake Ontario
    ]

    # Key cities / zones: (config_pos, label_line1, label_line2, color)
    CITY_MARKERS = [
        ("OUTBREAK_POS",      "San Diego",       "🧪 Outbreak",      "#ff4444"),
        ("WHITEHOUSE_POS",    "Washington D.C.", "🏛 White House",   "#ffffff"),
        ("LAB_POS",           "Atlanta, GA",     "💉 CDC",            "#00cfff"),
        ("MILITARY_BASE_POS", "Fort Bragg, NC",  "🎖 Military Base", "#00ff88"),
    ]

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(self, parent: tk.Widget, size: int = config.CANVAS_SIZE) -> None:
        """
        Initializes the canvas with ocean background and draws the base map.

        Args:
            parent: Tkinter parent widget.
            size: Canvas size in pixels (width and height).
        """
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=self.OCEAN_COLOR,
            highlightthickness=0,
        )
        self.canvas_size: int = size
        self.cell_size: float = size / config.GRID_SIZE
        self._rect_ids: Dict[Tuple[int, int], int] = {}
        self._cell_shape: Dict[Tuple[int, int], str] = {}  # "oval" | "rect"

        # Draw static map (layers 1-5)
        self._draw_usa_background()
        self._draw_zones()
        self._draw_legend()

    # ------------------------------------------------------------------
    # Static map
    # ------------------------------------------------------------------

    def _draw_usa_background(self) -> None:
        """Draws the continental U.S. polygon and state divisions."""
        cs = self.cell_size

        # Continental polygon
        pts = []
        for gx, gy in self.USA_POLYGON:
            pts.extend([gx * cs, gy * cs])
        self.create_polygon(
            pts,
            fill=self.LAND_COLOR,
            outline=self.LAND_BORDER_COLOR,
            width=1.5,
        )

        # State division lines (dashed)
        for line in self.STATE_REGION_LINES:
            pts = []
            for gx, gy in line:
                pts.extend([gx * cs, gy * cs])
            self.create_line(
                pts,
                fill=self.STATE_LINE_COLOR,
                width=0.8,
                dash=(4, 3),
            )

    def _draw_great_lakes(self) -> None:
        """Draws the Great Lakes as blue ovals."""
        cs = self.cell_size
        for cx, cy, rx, ry in self.GREAT_LAKES:
            self.create_oval(
                (cx - rx) * cs, (cy - ry) * cs,
                (cx + rx) * cs, (cy + ry) * cs,
                fill=self.LAKE_COLOR,
                outline="#2a6a9b",
                width=0.5,
            )

    def _draw_zones(self) -> None:
        """Draws key city markers with name and emoji."""
        cs = self.cell_size
        r = config.LAB_RADIUS * cs

        for attr, line1, line2, color in self.CITY_MARKERS:
            gx, gy = getattr(config, attr)
            px, py = gx * cs, gy * cs

            # Dashed circle
            self.create_oval(
                px - r, py - r, px + r, py + r,
                outline=color, fill="", width=1.5, dash=(3, 3),
            )
            # Center dot
            self.create_oval(
                px - 2, py - 2, px + 2, py + 2,
                fill=color, outline="",
            )
            # Label: city above, emoji/role below
            self.create_text(
                px, py - r - 10,
                text=line1, fill=color,
                font=("Consolas", 7, "bold"),
            )
            self.create_text(
                px, py - r - 1,
                text=line2, fill=color,
                font=("Consolas", 7),
            )

    def _draw_legend(self) -> None:
        """Draws the agent type legend in the bottom-left corner using real shapes."""
        cs = self.cell_size
        x0 = int(4 * cs)
        y0 = int(84 * cs)
        box = 8
        row_h = 14
        pad = 4

        total_h = len(self.LEGEND) * row_h + pad * 2
        self.create_rectangle(
            x0 - pad, y0 - pad,
            x0 + 75, y0 + total_h - pad,
            fill="#000000", outline="", stipple="gray50",
        )

        y = y0
        for label, color, shape in self.LEGEND:
            cx = x0 + box // 2
            cy = y + box // 2
            x1, y1 = x0, y
            x2, y2 = x0 + box, y + box

            if shape == "blob":
                self.create_oval(x1 - 1, y1 - 1, x2 + 1, y2 + 1,
                                 fill=color, outline="#5a4a00", width=1)
            elif shape == "square":
                self.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
            elif shape == "diamond":
                self.create_polygon(cx, y1, x2, cy, cx, y2, x1, cy,
                                    fill=color, outline="")
            elif shape == "circle_outlined":
                self.create_oval(x1, y1, x2, y2,
                                 fill=color, outline="#ffffff", width=1)
            else:
                self.create_oval(x1, y1, x2, y2, fill=color, outline="")

            self.create_text(
                x0 + box + 4, cy,
                text=label, anchor="w",
                fill="#dddddd", font=("Consolas", 7),
            )
            y += row_h

    # ------------------------------------------------------------------
    # Agent rendering (frame by frame)
    # ------------------------------------------------------------------

    def render(
        self,
        snapshot: Dict[Tuple[int, int], Dict[str, str]],
    ) -> None:
        """
        Updates visible agents from the Engine snapshot.

        Clears cells that no longer have an agent (deletes the item so
        the underlying map is visible) and draws/updates new ones.
        Agents below the overlay tag are inserted beneath it.

        Args:
            snapshot: Dict of {(x, y): {"color", "type", "role", "state"}} from World.
        """
        stale = set(self._rect_ids.keys()) - set(snapshot.keys())
        for pos in stale:
            self._clear_cell(pos)

        for pos, agent_data in snapshot.items():
            color     = agent_data.get("color", config.COLOR_NORMAL)
            agent_type = agent_data.get("type", "")
            role      = agent_data.get("role", "")
            state     = agent_data.get("state", "")
            self._draw_cell(pos, color, agent_type, role, state)

    # Shape key per role — used to detect when a recreate is needed
    _ROLE_SHAPE: Dict[str, str] = {
        "normal":    "circle",
        "scientist": "circle_outlined",
        "military":  "square",
        "politician":"diamond",
        "zombie":    "blob",
    }

    def _draw_cell(
        self,
        pos: Tuple[int, int],
        color: str,
        agent_type: str = "",
        role: str = "",
        state: str = "",
    ) -> None:
        """
        Draws or updates an agent using a shape that reflects its role:
          Zombie     → large circle with dark outline (blob)
          Military   → square  (angular, soldier-like)
          Politician → diamond (rotated square)
          Scientist  → circle with white outline
          Normal/Infected/Dead → plain circle
        """
        cs  = self.cell_size
        pad = max(1.0, cs * 0.1)
        x1  = pos[0] * cs + pad
        y1  = pos[1] * cs + pad
        x2  = pos[0] * cs + cs - pad
        y2  = pos[1] * cs + cs - pad
        cx  = (x1 + x2) / 2
        cy  = (y1 + y2) / 2

        # Determine canonical shape key
        if agent_type == "Zombie":
            shape = "blob"
        elif role == "military":
            shape = "square"
        elif role == "politician":
            shape = "diamond"
        elif role == "scientist":
            shape = "circle_outlined"
        else:
            shape = "circle"

        # Recreate if shape type changed
        if pos in self._rect_ids:
            if self._cell_shape.get(pos) != shape:
                self.delete(self._rect_ids[pos])
                del self._rect_ids[pos]
                del self._cell_shape[pos]
            else:
                self.itemconfig(self._rect_ids[pos], fill=color)
                return

        # ---- Create new canvas item ----
        if shape == "blob":
            # Zombie: large circle with menacing outline
            item_id = self.create_oval(
                x1 - 1, y1 - 1, x2 + 1, y2 + 1,
                fill=color, outline="#5a4a00", width=1.5,
            )
        elif shape == "square":
            # Military: sharp square
            item_id = self.create_rectangle(
                x1, y1, x2, y2,
                fill=color, outline="",
            )
        elif shape == "diamond":
            # Politician: rotated square (diamond)
            item_id = self.create_polygon(
                cx, y1,   # top
                x2, cy,   # right
                cx, y2,   # bottom
                x1, cy,   # left
                fill=color, outline="",
            )
        elif shape == "circle_outlined":
            # Scientist: circle with bright outline
            item_id = self.create_oval(
                x1, y1, x2, y2,
                fill=color, outline="#ffffff", width=1.2,
            )
        else:
            # Normal / infected / dead: plain circle
            item_id = self.create_oval(
                x1, y1, x2, y2,
                fill=color, outline="",
            )

        try:
            self.tag_lower(item_id, "overlay")
        except Exception:
            pass
        self._rect_ids[pos] = item_id
        self._cell_shape[pos] = shape

    def _clear_cell(self, pos: Tuple[int, int]) -> None:
        """Removes an agent's shape to expose the map."""
        if pos in self._rect_ids:
            self.delete(self._rect_ids[pos])
            del self._rect_ids[pos]
            self._cell_shape.pop(pos, None)

    def clear(self) -> None:
        """Removes all agent shapes (without touching the base map)."""
        for item_id in self._rect_ids.values():
            self.delete(item_id)
        self._rect_ids.clear()
        self._cell_shape.clear()

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

        # Semi-transparent dark veil
        self.create_rectangle(
            0, 0, w, h,
            fill=bg, outline="", stipple="gray75",
            tags="overlay",
        )
        # Decorative box
        self.create_rectangle(
            w // 4, h // 2 - 60, 3 * w // 4, h // 2 + 60,
            fill="#000000", outline=color, width=2, stipple="gray50",
            tags="overlay",
        )
        # Main result text
        self.create_text(
            w // 2, h // 2 - 18,
            text=title,
            fill=color,
            font=("Consolas", 20, "bold"),
            tags="overlay",
        )
        # Sub-text
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

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def pos_to_grid(self, pixel_x: int, pixel_y: int) -> Tuple[int, int]:
        """Converts pixel coordinates to grid cell."""
        grid_x = int(pixel_x / self.cell_size)
        grid_y = int(pixel_y / self.cell_size)
        return (
            max(0, min(config.GRID_SIZE - 1, grid_x)),
            max(0, min(config.GRID_SIZE - 1, grid_y)),
        )
