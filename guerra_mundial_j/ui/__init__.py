"""
ui — Paquete de interfaz gráfica Tkinter de la simulación.

Contiene todos los componentes visuales que permiten observar y controlar
la simulación en tiempo real. El loop de UI se actualiza cada UI_REFRESH_MS
milisegundos mediante Tkinter's after(), consumiendo snapshots del Engine.

Componentes:
    app.py          — App (Tk root): ventana principal, layout y loop de UI.
                      Conecta el Engine con los widgets visuales.
    grid_canvas.py  — GridCanvas: dibuja el grid 100×100 con un rectángulo
                      de color por cada agente. Incluye leyenda y marcadores
                      de zonas clave (LAB, Casa Blanca, Base Militar).
    control_panel.py — ControlPanel: botones Start/Pause/Reset/Batch y
                      sliders para ajustar parámetros en tiempo real.
    stats_panel.py  — StatsPanel: panel de estadísticas en tiempo real
                      (humanos, zombis, infectados, antídoto, tick, estrategia).
    event_log.py    — EventLog: log scrolleable de eventos con timestamp
                      y colores por tipo (muerte, infección, alerta, etc.).
"""

from ui.app import App

__all__ = ["App"]
