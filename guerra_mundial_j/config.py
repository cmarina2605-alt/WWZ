"""
config.py — Constantes globales de la simulación Guerra Mundial J.

Este fichero centraliza TODOS los parámetros configurables de la
simulación. Cualquier ajuste de comportamiento (velocidad, probabilidades,
tamaño del mundo, colores de la UI) se hace aquí, sin tocar la lógica
de los agentes ni del motor.

Secciones:
    - Dimensiones del mundo: tamaño del grid 2D.
    - Población inicial: número de humanos por rol y zombis al arrancar.
    - Localizaciones clave: posiciones fijas de LAB, Casa Blanca y base militar.
    - Parámetros de probabilidad: infección, huida, matar zombi.
    - Visión: radios de detección para humanos y zombis.
    - Tiempos: velocidad base de tick, intervalos de comprobación,
      ticks para el antídoto y período de incubación de infectados.
    - Colores UI: strings de color Tkinter por tipo de agente.
    - Parámetros de combate: bonus militar, umbrales de fuerza y edad.
    - Base de datos: ruta del fichero SQLite.
    - UI: dimensiones de ventana y frecuencia de refresco.
    - Estrategias: lista de estrategias disponibles para runs batch.
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
# Localizaciones clave del mapa de EEUU (x=oeste-este, y=norte-sur, grid 0-99)
# ---------------------------------------------------------------------------
OUTBREAK_POS: tuple = (5, 74)       # San Diego, CA — origen del brote (José)
LAB_POS: tuple = (68, 62)           # CDC Atlanta, GA — base científica
LAB_RADIUS: int = 3                 # Radio de detección del laboratorio (celdas)
WHITEHOUSE_POS: tuple = (80, 40)    # Washington D.C. — Casa Blanca
MILITARY_BASE_POS: tuple = (76, 55) # Fort Bragg, NC — base militar

# ---------------------------------------------------------------------------
# Colores del mapa geográfico (UI)
# ---------------------------------------------------------------------------
OCEAN_COLOR: str = "#0a2040"        # Fondo océano
LAND_COLOR: str = "#2d5a27"         # Territorio continental
LAND_BORDER_COLOR: str = "#4a8a42"  # Contorno y fronteras estatales
LAKE_COLOR: str = "#1a4a6b"         # Grandes Lagos

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
