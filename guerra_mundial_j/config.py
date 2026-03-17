"""
config.py — Constantes globales de la simulación Guerra Mundial J.

Todas las constantes de configuración están centralizadas aquí para
facilitar el ajuste de parámetros sin tocar lógica de negocio.
"""

# ---------------------------------------------------------------------------
# Dimensiones del mundo
# ---------------------------------------------------------------------------
GRID_SIZE: int = 100          # Lado del grid cuadrado (celdas)

# ---------------------------------------------------------------------------
# Población inicial
# ---------------------------------------------------------------------------
NUM_HUMANS: int = 100         # Número de humanos al inicio
NUM_ZOMBIES: int = 1          # Número de zombis al inicio
NUM_SCIENTISTS: int = 5       # Subconjunto de humanos tipo Scientist
NUM_MILITARY: int = 10        # Subconjunto de humanos tipo Military
NUM_POLITICIANS: int = 2      # Subconjunto de humanos tipo Politician

# ---------------------------------------------------------------------------
# Localizaciones clave del mapa (x, y)
# ---------------------------------------------------------------------------
LAB_POS: tuple = (80, 80)          # Base científica (esquina inferior-derecha)
LAB_RADIUS: int = 3                # Radio de detección de la base en celdas
WHITEHOUSE_POS: tuple = (90, 10)   # Casa Blanca (arriba-derecha)
MILITARY_BASE_POS: tuple = (10, 90) # Base militar (abajo-izquierda)

# ---------------------------------------------------------------------------
# Parámetros de probabilidad
# ---------------------------------------------------------------------------
P_INFECT: float = 0.4         # Probabilidad de infección en encuentro
P_KILL_ZOMBIE: float = 0.2    # Probabilidad de que un humano mate al zombi
P_ESCAPE: float = 0.3         # Probabilidad base de escapar

# ---------------------------------------------------------------------------
# Visión / rango de detección (en celdas)
# ---------------------------------------------------------------------------
VISION_HUMAN: int = 10        # Radio de visión de un humano
VISION_ZOMBIE: int = 15       # Radio de visión de un zombi

# ---------------------------------------------------------------------------
# Tiempos
# ---------------------------------------------------------------------------
TICK_SPEED: float = 0.1       # Segundos entre ticks de cada agente (base)
WIN_CHECK_INTERVAL: float = 1.0   # Segundos entre comprobaciones de victoria
ANTIDOTE_TICKS: int = 500     # Ticks necesarios para que un Scientist complete antídoto
INFECTION_DELAY_TICKS: int = 25   # Ticks de incubación antes de que un infectado se convierta

# ---------------------------------------------------------------------------
# Colores de la UI (Tkinter color strings)
# ---------------------------------------------------------------------------
COLOR_ZOMBIE: str = "yellow"
COLOR_NORMAL: str = "red"
COLOR_MILITARY: str = "green"
COLOR_SCIENTIST: str = "purple"
COLOR_POLITICIAN: str = "blue"
COLOR_INFECTED: str = "orange"
COLOR_DEAD: str = "gray"
COLOR_EMPTY: str = "#1a1a2e"   # Fondo oscuro

# ---------------------------------------------------------------------------
# Parámetros de combate
# ---------------------------------------------------------------------------
FORCE_MILITARY_BONUS: int = 20
FORCE_FLEE_THRESHOLD: int = 60  # Por encima de este valor Military no huye
AGE_PENALTY_THRESHOLD: int = 60 # A partir de esta edad la fuerza decae

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
DB_PATH: str = "simulations.db"

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
WINDOW_WIDTH: int = 1200
WINDOW_HEIGHT: int = 700
CANVAS_SIZE: int = 600        # Tamaño en píxeles del canvas del grid
UI_REFRESH_MS: int = 100      # Milisegundos entre refrescos de la UI

# ---------------------------------------------------------------------------
# Estrategias disponibles para batch runs
# ---------------------------------------------------------------------------
STRATEGIES: list[str] = ["random", "flee", "group", "military_first"]
