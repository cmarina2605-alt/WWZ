"""
event_log.py — Widget de log de eventos de la simulación.

EventLog muestra mensajes en tiempo real con timestamp,
permitiendo hacer scroll para ver el historial.
"""

import tkinter as tk
from datetime import datetime
from typing import Optional


class EventLog(tk.Frame):
    """
    Panel de log de eventos con scroll automático.

    Muestra mensajes de eventos de la simulación (infecciones,
    muertes, antídoto, alertas) con timestamp. Los nuevos mensajes
    se insertan al principio (más recientes arriba).

    Attributes:
        _text (tk.Text): Widget de texto con scrollbar.
        max_lines (int): Máximo de líneas antes de hacer pruning.
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
        Inicializa el panel de log.

        Args:
            parent: Widget padre.
            max_lines: Número máximo de líneas a mantener en el log.
        """
        super().__init__(parent, bg="#0d1117", padx=3, pady=3)
        self.max_lines: int = max_lines
        self._build_widget()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def _build_widget(self) -> None:
        """Construye el widget de texto con scrollbar."""
        # Título
        title = tk.Label(
            self,
            text="📋 LOG DE EVENTOS",
            bg="#0d1117",
            fg="#58a6ff",
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        title.pack(fill=tk.X, pady=(0, 2))

        # Frame contenedor texto + scroll
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

        # Configurar tags de color
        for tag, color in self.TAG_COLORS.items():
            self._text.tag_config(tag, foreground=color)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def add_event(self, msg: str, tag: Optional[str] = None) -> None:
        """
        Añade un mensaje al log con timestamp.

        El mensaje se inserta al principio del texto (más reciente arriba).
        Detecta automáticamente el tipo según emojis en el mensaje.

        Args:
            msg: Mensaje a mostrar.
            tag: Tag de color opcional. Si None, se detecta automáticamente.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"

        # Detección automática de tipo por contenido
        if tag is None:
            tag = self._detect_tag(msg)

        self._text.config(state=tk.NORMAL)
        self._text.insert("1.0", line, tag)
        self._prune()
        self._text.config(state=tk.DISABLED)

    def clear(self) -> None:
        """Limpia todo el contenido del log."""
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _detect_tag(self, msg: str) -> str:
        """
        Detecta el tag de color apropiado según el contenido del mensaje.

        Args:
            msg: Mensaje a analizar.

        Returns:
            Nombre del tag de color.
        """
        if any(e in msg for e in ("💀", "murió", "dead")):
            return "death"
        if any(e in msg for e in ("🧟", "infectado", "infect")):
            return "infection"
        if any(e in msg for e in ("🧪", "antídoto", "antidote")):
            return "antidote"
        if any(e in msg for e in ("📨", "alerta", "alert", "Casa Blanca")):
            return "alert"
        if any(e in msg for e in ("🏃", "escapó", "escape")):
            return "escape"
        if any(e in msg for e in ("▶", "⏸", "🔄", "✅", "🔁")):
            return "system"
        return "default"

    def _prune(self) -> None:
        """
        Elimina las líneas más antiguas si se supera max_lines.
        """
        line_count = int(self._text.index(tk.END).split(".")[0]) - 1
        if line_count > self.max_lines:
            excess = line_count - self.max_lines
            self._text.delete(f"{self.max_lines + 1}.0", tk.END)
