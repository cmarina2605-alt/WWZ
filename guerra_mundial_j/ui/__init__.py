"""
ui — Tkinter graphical interface package for the simulation.

Contains all visual components for observing and controlling the simulation
in real time. The UI loop updates every UI_REFRESH_MS milliseconds via
Tkinter's after(), consuming Engine snapshots.

Components:
    app.py           — App (Tk root): main window, layout, and UI loop.
                       Connects the Engine with visual widgets.
    grid_canvas.py   — GridCanvas: draws the 100×100 grid with a colored
                       rectangle per agent. Includes legend and key zone
                       markers (LAB, White House, Military Base).
    control_panel.py — ControlPanel: Start/Pause/Reset/Batch buttons and
                       sliders for real-time parameter adjustment.
    stats_panel.py   — StatsPanel: real-time statistics panel
                       (humans, zombies, infected, antidote, tick, strategy).
    event_log.py     — EventLog: scrollable event log with timestamps
                       and colors by type (death, infection, alert, etc.).
"""

from ui.app import App

__all__ = ["App"]
