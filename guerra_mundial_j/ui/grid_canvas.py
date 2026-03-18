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
    # Agent legend
    # ------------------------------------------------------------------
    LEGEND = [
        ("Normal",    config.COLOR_NORMAL),
        ("Military",  config.COLOR_MILITARY),
        ("Scientist", config.COLOR_SCIENTIST),
        ("Politician",config.COLOR_POLITICIAN),
        ("Zombie",    config.COLOR_ZOMBIE),
        ("Infected",  config.COLOR_INFECTED),
    ]

    # ------------------------------------------------------------------
    # Map geometry
    # ------------------------------------------------------------------

    # Approximate contour of the continental U.S.
    # (grid coords 0-99; x=west→east, y=north→south)
    USA_POLYGON = [
        # Northwest coast (Washington) → northern border
        (3, 8), (8, 5), (15, 3), (25, 2), (38, 2), (50, 2), (62, 2),
        # Northern border → northeast (Maine)
        (72, 2), (82, 3), (88, 5), (92, 8), (93, 11), (93, 16), (92, 20),
        # East coast going south
        (91, 24), (92, 28), (91, 32), (90, 36), (89, 40), (90, 44),
        (88, 48), (86, 52), (84, 56), (82, 60), (81, 63),
        # Florida Peninsula
        (80, 67), (78, 72), (76, 78), (74, 84), (72, 90), (70, 95),
        (71, 97), (73, 96), (75, 92), (75, 87), (76, 83),
        # Gulf of Mexico coast (FL → TX)
        (75, 80), (73, 82), (70, 83), (66, 83), (62, 84),
        (58, 84), (54, 85), (50, 86), (46, 87), (42, 90),
        # Texas / Mexico border
        (40, 90), (38, 88), (35, 83), (32, 78), (28, 73), (24, 71),
        # Southwest border (US–Mexico)
        (20, 74), (16, 77), (12, 78), (8, 78), (5, 78), (3, 78),
        # Pacific coast going north
        (2, 72), (2, 62), (2, 52), (2, 42), (2, 32), (2, 22), (2, 15), (3, 8),
    ]

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
        """Draws the agent type legend in the bottom-left corner."""
        cs = self.cell_size
        # Anchor at bottom-left corner (within the territory)
        x0 = int(4 * cs)
        y0 = int(84 * cs)
        box = 8
        row_h = 13
        pad = 4

        # Semi-opaque background (stipple simulates transparency; Tkinter doesn't support alpha in hex)
        total_h = len(self.LEGEND) * row_h + pad * 2
        self.create_rectangle(
            x0 - pad, y0 - pad,
            x0 + 70, y0 + total_h - pad,
            fill="#000000", outline="", stipple="gray50",
        )

        y = y0
        for label, color in self.LEGEND:
            self.create_rectangle(x0, y, x0 + box, y + box, fill=color, outline="")
            self.create_text(
                x0 + box + 3, y + box // 2,
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

        Clears cells that no longer have an agent (deletes the rectangle so
        the underlying map is visible) and draws/updates new ones.

        Args:
            snapshot: Dict of {(x, y): {"color": str, ...}} from World.
        """
        stale = set(self._rect_ids.keys()) - set(snapshot.keys())
        for pos in stale:
            self._clear_cell(pos)

        for pos, agent_data in snapshot.items():
            color = agent_data.get("color", config.COLOR_NORMAL)
            self._draw_cell(pos, color)

    def _draw_cell(self, pos: Tuple[int, int], color: str) -> None:
        """Draws or updates an agent's rectangle."""
        x1 = pos[0] * self.cell_size
        y1 = pos[1] * self.cell_size
        x2 = x1 + self.cell_size
        y2 = y1 + self.cell_size

        if pos in self._rect_ids:
            self.itemconfig(self._rect_ids[pos], fill=color)
        else:
            rect_id = self.create_rectangle(
                x1, y1, x2, y2,
                fill=color,
                outline="",
            )
            self._rect_ids[pos] = rect_id

    def _clear_cell(self, pos: Tuple[int, int]) -> None:
        """Removes an agent's rectangle to expose the map."""
        if pos in self._rect_ids:
            self.delete(self._rect_ids[pos])
            del self._rect_ids[pos]

    def clear(self) -> None:
        """Removes all agent rectangles (without touching the base map)."""
        for rect_id in self._rect_ids.values():
            self.delete(rect_id)
        self._rect_ids.clear()

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
