"""
event_log.py — Simulation event log widget.

EventLog is a scrollable text panel that displays in real time all
significant events occurring during the simulation, with timestamps
and colors differentiated by event type.

Event sources:
    - world.pop_events() in the UI loop → infections, deaths, escapes,
      national alerts, antidote creation, outbreak events (José).
    - app.py directly → control events (start, pause, reset, batch).

Colors by type:
    Light red   — deaths (💀 died, dead)
    Orange      — infections (🧟 infected)
    Light green — antidote completed (💉)
    Light blue  — national alerts (📨 White House)
    Pale green  — escapes (🏃)
    Gray        — system events (start, pause, reset)
    White/gray  — any other event

Most recent messages appear at the top (insert at position 1.0).
A maximum of max_lines=200 entries is kept to avoid memory saturation.
"""

import tkinter as tk
from datetime import datetime
from typing import Optional


class EventLog(tk.Frame):
    """
    Event log panel with auto-scroll.

    Displays simulation event messages (infections, deaths, antidote,
    alerts) with timestamps. New messages are inserted at the top
    (most recent first).

    Attributes:
        _text (tk.Text): Text widget with scrollbar.
        max_lines (int): Maximum lines before pruning.
    """

    # Colores para tipos de mensajes especiales
    TAG_COLORS = {
        "death": "#ff6b6b",
        "infection": "#ffa500",
        "antidote": "#00ff88",
        "alert": "#87ceeb",
        "escape": "#98fb98",
        "default": "#cccccc",
        "system": "#888888",
    }

    def __init__(
        self,
        parent: tk.Widget,
        max_lines: int = 200,
    ) -> None:
        """
        Initializes the log panel.

        Args:
            parent: Parent widget.
            max_lines: Maximum number of lines to keep in the log.
        """
        super().__init__(parent, bg="#0d1117", padx=3, pady=3)
        self.max_lines: int = max_lines
        self._build_widget()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_widget(self) -> None:
        """Builds the text widget with scrollbar."""
        # Title
        title = tk.Label(
            self,
            text="📋 EVENT LOG",
            bg="#0d1117",
            fg="#58a6ff",
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        title.pack(fill=tk.X, pady=(0, 2))

        # Text + scroll container frame
        text_frame = tk.Frame(self, bg="#0d1117")
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame, bg="#21262d", troughcolor="#161b22")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._text = tk.Text(
            text_frame,
            bg="#0d1117",
            fg="#cccccc",
            font=("Consolas", 8),
            wrap=tk.WORD,
            state=tk.DISABLED,
            yscrollcommand=scrollbar.set,
            highlightthickness=0,
            relief=tk.FLAT,
            cursor="arrow",
        )
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self._text.yview)

        # Configure color tags
        for tag, color in self.TAG_COLORS.items():
            self._text.tag_config(tag, foreground=color)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_event(self, msg: str, tag: Optional[str] = None) -> None:
        """
        Adds a message to the log with a timestamp.

        The message is inserted at the top of the text (most recent first).
        Automatically detects the type based on emojis in the message.

        Args:
            msg: Message to display.
            tag: Optional color tag. If None, detected automatically.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"

        # Automatic type detection by content
        if tag is None:
            tag = self._detect_tag(msg)

        self._text.config(state=tk.NORMAL)
        self._text.insert("1.0", line, tag)
        self._prune()
        self._text.config(state=tk.DISABLED)

    def clear(self) -> None:
        """Clears all log content."""
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _detect_tag(self, msg: str) -> str:
        """
        Detects the appropriate color tag based on message content.

        Args:
            msg: Message to analyze.

        Returns:
            Color tag name.
        """
        if any(e in msg for e in ("💀", "died", "dead")):
            return "death"
        if any(e in msg for e in ("🧟", "infected", "infect")):
            return "infection"
        if any(e in msg for e in ("🧪", "antidote", "ANTIDOTE")):
            return "antidote"
        if any(e in msg for e in ("📨", "alert", "White House")):
            return "alert"
        if any(e in msg for e in ("🏃", "escaped", "escape")):
            return "escape"
        if any(e in msg for e in ("▶", "⏸", "🔄", "✅", "🔁")):
            return "system"
        return "default"

    def _prune(self) -> None:
        """
        Removes the oldest lines when max_lines is exceeded.
        """
        line_count = int(self._text.index(tk.END).split(".")[0]) - 1
        if line_count > self.max_lines:
            excess = line_count - self.max_lines
            self._text.delete(f"{self.max_lines + 1}.0", tk.END)
