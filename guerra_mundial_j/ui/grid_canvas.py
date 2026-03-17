"""
grid_canvas.py — Canvas Tkinter que dibuja el mapa de EE.UU. de la simulación.

GridCanvas renderiza el estado del mundo sobre un mapa geográfico aproximado
de los Estados Unidos continentales. El mapa se dibuja una sola vez al iniciar
(océano, territorio, estados, Grandes Lagos, ciudades clave) y los agentes
se superponen frame a frame como rectángulos de color.

Capas de renderizado (de abajo a arriba):
    1. Fondo océano (bg OCEAN_COLOR).
    2. Polígono continental de EE.UU. (LAND_COLOR).
    3. Líneas de divisiones estatales (STATE_LINE_COLOR, punteadas).
    4. Grandes Lagos (LAKE_COLOR).
    5. Marcadores de ciudades clave (San Diego, Washington D.C., Atlanta, Fort Bragg).
    6. Leyenda de colores de agentes (esquina superior izquierda).
    7. Rectángulos de agentes — se actualizan cada frame sin recrear los layers inferiores.

Colores de agentes:
    Rojo     — Normal
    Verde    — Military
    Morado   — Scientist
    Azul     — Politician
    Amarillo — Zombie (¡todos son José!)
    Naranja  — Infectado (incubación)
    Gris     — Muerto

Optimización:
    Los rectángulos de agentes se reutilizan entre frames (itemconfig en lugar
    de delete+create). Al limpiar una celda, el rectángulo se elimina del todo
    para que el mapa subyacente quede visible.
"""

import tkinter as tk
from typing import Dict, Tuple, Any

import config


class GridCanvas(tk.Canvas):
    """
    Canvas que visualiza el grid de agentes sobre un mapa de EE.UU.

    Attributes:
        canvas_size (int): Tamaño en píxeles del canvas cuadrado.
        cell_size (float): Tamaño en píxeles de cada celda del grid.
        _rect_ids (Dict): Cache de IDs de rectángulos de agentes para reusar.
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
    # Leyenda de agentes
    # ------------------------------------------------------------------
    LEGEND = [
        ("Normal",     config.COLOR_NORMAL),
        ("Militar",    config.COLOR_MILITARY),
        ("Científico", config.COLOR_SCIENTIST),
        ("Político",   config.COLOR_POLITICIAN),
        ("Zombi",      config.COLOR_ZOMBIE),
        ("Infectado",  config.COLOR_INFECTED),
    ]

    # ------------------------------------------------------------------
    # Geometría del mapa
    # ------------------------------------------------------------------

    # Contorno aproximado de los EE.UU. continentales
    # (coords de grid 0-99; x=oeste→este, y=norte→sur)
    USA_POLYGON = [
        # Costa noroeste (Washington) → frontera norte
        (3, 8), (8, 5), (15, 3), (25, 2), (38, 2), (50, 2), (62, 2),
        # Frontera norte → noreste (Maine)
        (72, 2), (82, 3), (88, 5), (92, 8), (93, 11), (93, 16), (92, 20),
        # Costa este hacia el sur
        (91, 24), (92, 28), (91, 32), (90, 36), (89, 40), (90, 44),
        (88, 48), (86, 52), (84, 56), (82, 60), (81, 63),
        # Península de Florida
        (80, 67), (78, 72), (76, 78), (74, 84), (72, 90), (70, 95),
        (71, 97), (73, 96), (75, 92), (75, 87), (76, 83),
        # Costa del Golfo de México (FL → TX)
        (75, 80), (73, 82), (70, 83), (66, 83), (62, 84),
        (58, 84), (54, 85), (50, 86), (46, 87), (42, 90),
        # Frontera Texas / México
        (40, 90), (38, 88), (35, 83), (32, 78), (28, 73), (24, 71),
        # Frontera suroeste (US–México)
        (20, 74), (16, 77), (12, 78), (8, 78), (5, 78), (3, 78),
        # Costa Pacífica hacia el norte
        (2, 72), (2, 62), (2, 52), (2, 42), (2, 32), (2, 22), (2, 15), (3, 8),
    ]

    # Líneas aproximadas de divisiones estatales (trazos punteados)
    STATE_REGION_LINES = [
        # Frontera oriental de los estados del Pacífico (CA / NV-AZ)
        [(15, 3), (14, 20), (14, 40), (14, 60), (14, 78)],
        # Frontera oriental de los estados Montañosos (CO / Grandes Llanuras)
        [(35, 2), (34, 20), (33, 40), (33, 60), (35, 83)],
        # Río Misisipi / divisoria central
        [(56, 2), (55, 20), (55, 40), (55, 60), (54, 85)],
        # Frontera de los estados del Este
        [(80, 5), (80, 20), (80, 40), (80, 60), (80, 64)],
    ]

    # Grandes Lagos (cx, cy, rx, ry) en coords de grid
    GREAT_LAKES = [
        (58, 17, 8, 4),  # Lake Superior
        (63, 27, 4, 8),  # Lake Michigan
        (70, 23, 6, 5),  # Lake Huron
        (75, 29, 5, 3),  # Lake Erie
        (80, 26, 4, 3),  # Lake Ontario
    ]

    # Ciudades / zonas clave: (config_pos, label_línea1, label_línea2, color)
    CITY_MARKERS = [
        ("OUTBREAK_POS",      "San Diego",      "🧪 Brote",       "#ff4444"),
        ("WHITEHOUSE_POS",    "Washington D.C.", "🏛 Casa Blanca", "#ffffff"),
        ("LAB_POS",           "Atlanta, GA",    "💉 CDC",          "#00cfff"),
        ("MILITARY_BASE_POS", "Fort Bragg, NC", "🎖 Base Militar", "#00ff88"),
    ]

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(self, parent: tk.Widget, size: int = config.CANVAS_SIZE) -> None:
        """
        Inicializa el canvas con fondo océano y dibuja el mapa base.

        Args:
            parent: Widget padre de Tkinter.
            size: Tamaño en píxeles del canvas (ancho y alto).
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

        # Dibujar mapa estático (capas 1-6)
        self._draw_usa_background()
        self._draw_great_lakes()
        self._draw_zones()
        self._draw_legend()

    # ------------------------------------------------------------------
    # Mapa estático
    # ------------------------------------------------------------------

    def _draw_usa_background(self) -> None:
        """Dibuja el polígono continental de EE.UU. y las divisiones estatales."""
        cs = self.cell_size

        # Polígono continental
        pts = []
        for gx, gy in self.USA_POLYGON:
            pts.extend([gx * cs, gy * cs])
        self.create_polygon(
            pts,
            fill=self.LAND_COLOR,
            outline=self.LAND_BORDER_COLOR,
            width=1.5,
        )

        # Líneas de divisiones estatales (punteadas)
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
        """Dibuja los Grandes Lagos como óvalos azules."""
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
        """Dibuja los marcadores de ciudades clave con nombre y emoji."""
        cs = self.cell_size
        r = config.LAB_RADIUS * cs

        for attr, line1, line2, color in self.CITY_MARKERS:
            gx, gy = getattr(config, attr)
            px, py = gx * cs, gy * cs

            # Círculo punteado
            self.create_oval(
                px - r, py - r, px + r, py + r,
                outline=color, fill="", width=1.5, dash=(3, 3),
            )
            # Punto central
            self.create_oval(
                px - 2, py - 2, px + 2, py + 2,
                fill=color, outline="",
            )
            # Etiqueta: ciudad arriba, emoji/rol abajo
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
        """Dibuja la leyenda de tipos de agente en la esquina inferior izquierda."""
        cs = self.cell_size
        # Ancla en la esquina inferior izquierda (dentro del territorio)
        x0 = int(4 * cs)
        y0 = int(84 * cs)
        box = 8
        row_h = 13
        pad = 4

        # Fondo semitransparente
        total_h = len(self.LEGEND) * row_h + pad * 2
        self.create_rectangle(
            x0 - pad, y0 - pad,
            x0 + 70, y0 + total_h - pad,
            fill="#00000088", outline="", stipple="gray50",
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
    # Renderizado de agentes (frame a frame)
    # ------------------------------------------------------------------

    def render(
        self,
        snapshot: Dict[Tuple[int, int], Dict[str, str]],
    ) -> None:
        """
        Actualiza los agentes visibles a partir del snapshot del Engine.

        Limpia celdas que ya no tienen agente (delete del rectángulo para
        que el mapa subyacente sea visible) y dibuja/actualiza las nuevas.

        Args:
            snapshot: Dict de {(x, y): {"color": str, ...}} del World.
        """
        stale = set(self._rect_ids.keys()) - set(snapshot.keys())
        for pos in stale:
            self._clear_cell(pos)

        for pos, agent_data in snapshot.items():
            color = agent_data.get("color", config.COLOR_NORMAL)
            self._draw_cell(pos, color)

    def _draw_cell(self, pos: Tuple[int, int], color: str) -> None:
        """Dibuja o actualiza el rectángulo de un agente."""
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
        """Elimina el rectángulo de un agente para exponer el mapa."""
        if pos in self._rect_ids:
            self.delete(self._rect_ids[pos])
            del self._rect_ids[pos]

    def clear(self) -> None:
        """Elimina todos los rectángulos de agentes (sin tocar el mapa base)."""
        for rect_id in self._rect_ids.values():
            self.delete(rect_id)
        self._rect_ids.clear()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def pos_to_grid(self, pixel_x: int, pixel_y: int) -> Tuple[int, int]:
        """Convierte coordenadas de píxel a celda del grid."""
        grid_x = int(pixel_x / self.cell_size)
        grid_y = int(pixel_y / self.cell_size)
        return (
            max(0, min(config.GRID_SIZE - 1, grid_x)),
            max(0, min(config.GRID_SIZE - 1, grid_y)),
        )
