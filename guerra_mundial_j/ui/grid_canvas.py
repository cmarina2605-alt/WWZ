"""
grid_canvas.py — Canvas Tkinter que dibuja el grid de la simulación.

GridCanvas renderiza el estado del mundo como una cuadrícula de
rectángulos coloreados según el tipo y estado de cada agente.
"""

import tkinter as tk
from typing import Dict, Tuple, Any

import config


class GridCanvas(tk.Canvas):
    """
    Canvas que visualiza el grid de agentes de la simulación.

    Cada celda del grid se representa como un rectángulo cuyo color
    indica el tipo y estado del agente que la ocupa. Las celdas
    vacías se muestran con el color de fondo.

    El tamaño de cada celda se calcula automáticamente para que el
    grid completo encaje en el canvas.

    Attributes:
        canvas_size (int): Tamaño en píxeles del canvas (cuadrado).
        cell_size (float): Tamaño en píxeles de cada celda.
        _rect_ids (Dict): Cache de IDs de rectángulos para reusar.
    """

    def __init__(self, parent: tk.Widget, size: int = config.CANVAS_SIZE) -> None:
        """
        Inicializa el canvas con fondo oscuro.

        Args:
            parent: Widget padre de Tkinter.
            size: Tamaño en píxeles del canvas (ancho y alto).
        """
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=config.COLOR_EMPTY,
            highlightthickness=0,
        )
        self.canvas_size: int = size
        self.cell_size: float = size / config.GRID_SIZE
        self._rect_ids: Dict[Tuple[int, int], int] = {}
        self._draw_grid_lines()

    # ------------------------------------------------------------------
    # Inicialización visual
    # ------------------------------------------------------------------

    def _draw_grid_lines(self) -> None:
        """
        Dibuja las líneas de la cuadrícula como referencia visual.

        Solo dibuja líneas si la celda es suficientemente grande
        (≥ 4 píxeles) para no saturar visualmente.
        """
        if self.cell_size < 4:
            return

        for i in range(config.GRID_SIZE + 1):
            coord = i * self.cell_size
            # Líneas verticales
            self.create_line(coord, 0, coord, self.canvas_size, fill="#2a2a3e", width=0.5)
            # Líneas horizontales
            self.create_line(0, coord, self.canvas_size, coord, fill="#2a2a3e", width=0.5)

    # ------------------------------------------------------------------
    # Renderizado
    # ------------------------------------------------------------------

    def render(
        self,
        snapshot: Dict[Tuple[int, int], Dict[str, str]],
    ) -> None:
        """
        Renderiza el estado del grid a partir de un snapshot.

        Para cada posición con agente en el snapshot, dibuja o actualiza
        un rectángulo con el color correspondiente. Las celdas que ya no
        tienen agente se limpian.

        Args:
            snapshot: Dict de {(x, y): {"type": str, "role": str,
                      "state": str, "color": str}} generado por
                      World.get_state_snapshot().
        """
        # Detectar celdas que ya no tienen agente
        stale = set(self._rect_ids.keys()) - set(snapshot.keys())
        for pos in stale:
            self._clear_cell(pos)

        # Dibujar/actualizar celdas con agentes
        for pos, agent_data in snapshot.items():
            color = agent_data.get("color", config.COLOR_NORMAL)
            self._draw_cell(pos, color)

    def _draw_cell(self, pos: Tuple[int, int], color: str) -> None:
        """
        Dibuja o actualiza el rectángulo de una celda.

        Si ya existe un rectángulo para esa posición, solo actualiza
        el color. Si no, crea uno nuevo.

        Args:
            pos: Posición (x, y) en el grid.
            color: Color de relleno del rectángulo.
        """
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
                outline="",  # Sin borde para mejor rendimiento
            )
            self._rect_ids[pos] = rect_id

    def _clear_cell(self, pos: Tuple[int, int]) -> None:
        """
        Limpia una celda (la pone en color de fondo).

        Args:
            pos: Posición (x, y) a limpiar.
        """
        if pos in self._rect_ids:
            self.itemconfig(self._rect_ids[pos], fill=config.COLOR_EMPTY)
            del self._rect_ids[pos]

    def clear(self) -> None:
        """
        Limpia todo el canvas, eliminando todos los rectángulos dibujados.
        """
        for rect_id in self._rect_ids.values():
            self.delete(rect_id)
        self._rect_ids.clear()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def pos_to_grid(self, pixel_x: int, pixel_y: int) -> Tuple[int, int]:
        """
        Convierte coordenadas de píxel a coordenadas de grid.

        Útil para detectar clics del usuario sobre el canvas.

        Args:
            pixel_x: Coordenada X en píxeles.
            pixel_y: Coordenada Y en píxeles.

        Returns:
            Tupla (grid_x, grid_y) correspondiente.
        """
        grid_x = int(pixel_x / self.cell_size)
        grid_y = int(pixel_y / self.cell_size)
        return (
            max(0, min(config.GRID_SIZE - 1, grid_x)),
            max(0, min(config.GRID_SIZE - 1, grid_y)),
        )
