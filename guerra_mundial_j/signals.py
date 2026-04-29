"""
signals.py — Module-level threading signals for inter-thread communication.

Centralizes all simulation-wide threading.Event objects in one place.
Previously used a Singleton metaclass, but since the rest of the codebase
accesses them as module-level variables anyway, a simple module suffices.

Signals:
    game_over       — Set when the simulation ends (any win/loss condition).
    antidote_ready  — Set when a Scientist completes the antidote.
    national_alert  — Set when a Politician issues an emergency alert.
    pause_event     — Controls pause/resume (set = running, clear = paused).

Usage:
    from signals import game_over, antidote_ready, reset_all
    game_over.set()
    reset_all()
"""

import threading

game_over: threading.Event = threading.Event()
antidote_ready: threading.Event = threading.Event()
national_alert: threading.Event = threading.Event()
pause_event: threading.Event = threading.Event()
pause_event.set()  # Agents run by default


def reset_all() -> None:
    """
    Resets all signals to their default state for a new simulation.

    Called by Engine.reset() instead of manually clearing each event.
    """
    game_over.clear()
    antidote_ready.clear()
    national_alert.clear()
    pause_event.set()
