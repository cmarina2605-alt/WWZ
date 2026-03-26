"""
config.py — Global constants for the Guerra Mundial J simulation.

This file centralizes ALL configurable parameters of the simulation.
Any behavior adjustment (speed, probabilities, world size, UI colors)
is made here, without touching the agent or engine logic.

Sections:
    - World dimensions: 2D grid size.
    - Initial population: number of humans per role and zombies at start.
    - Key locations: fixed positions of LAB, White House and military base.
    - Probability parameters: infection, escape, kill zombie.
    - Vision: detection radii for humans and zombies.
    - Timing: base tick speed, check intervals,
      ticks for the antidote and incubation period for infected agents.
    - UI colors: Tkinter color strings per agent type.
    - Combat parameters: military bonus, force and age thresholds.
    - Database: path to the SQLite file.
    - UI: window dimensions and refresh rate.
    - Strategies: list of available strategies for batch runs.
"""

# ---------------------------------------------------------------------------
# World dimensions
# ---------------------------------------------------------------------------
GRID_SIZE: int = 100          # Side of the square grid (cells)

# ---------------------------------------------------------------------------
# Initial population
# ---------------------------------------------------------------------------
NUM_HUMANS: int = 100         # Number of humans at the start
NUM_ZOMBIES: int = 3          # Number of zombies at the start
NUM_SCIENTISTS: int = 5       # Subset of humans of type Scientist
NUM_MILITARY: int = 6         # Subset of humans of type Military
NUM_POLITICIANS: int = 2      # Subset of humans of type Politician

# ---------------------------------------------------------------------------
# Key locations on the US map (x=west-east, y=north-south, grid 0-99)
# ---------------------------------------------------------------------------
OUTBREAK_POS: tuple = (5, 74)       # San Diego, CA — outbreak origin (José)
LAB_POS: tuple = (68, 62)           # CDC Atlanta, GA — science base
LAB_RADIUS: int = 3                 # Laboratory detection radius (cells)
WHITEHOUSE_POS: tuple = (80, 40)    # Washington D.C. — White House
MILITARY_BASE_POS: tuple = (76, 55) # Fort Bragg, NC — military base

# ---------------------------------------------------------------------------
# Continental U.S. polygon for the land mask (grid coords 0-99)
# Used by World to block movement through ocean cells.
# ---------------------------------------------------------------------------
USA_POLYGON: list = [
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

# ---------------------------------------------------------------------------
# Geographic map colors (UI)
# ---------------------------------------------------------------------------
OCEAN_COLOR: str = "#061828"        # Deep ocean background
LAND_COLOR: str = "#1c3318"         # Dark terrain green
LAND_BORDER_COLOR: str = "#2e5a28"  # Slightly lighter border
STATE_LINE_COLOR: str = "#2a4e24"   # Subtle state divisions
LAKE_COLOR: str = "#0c2e48"         # Deep lake blue

# ---------------------------------------------------------------------------
# Probability parameters
# ---------------------------------------------------------------------------
P_INFECT: float = 0.40        # Infection probability in an encounter
P_KILL_ZOMBIE: float = 0.05   # Probability that a human kills the zombie
P_ESCAPE: float = 0.20        # Base escape probability

# ---------------------------------------------------------------------------
# Vision / detection range (in cells)
# ---------------------------------------------------------------------------
VISION_HUMAN: int = 10        # Human vision radius
VISION_ZOMBIE: int = 15       # Zombie vision radius

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
TICK_SPEED: float = 0.1       # Seconds between ticks per agent (base)
WIN_CHECK_INTERVAL: float = 1.0   # Seconds between victory condition checks
ANTIDOTE_TICKS: int = 3000    # Ticks needed for a Scientist to complete the antidote
INFECTION_DELAY_TICKS: int = 25   # Incubation ticks before an infected agent turns

# ---------------------------------------------------------------------------
# UI colors (hex)
# ---------------------------------------------------------------------------
COLOR_ZOMBIE: str = "#00ff41"      # Neon matrix green — stands out hard
COLOR_NORMAL: str = "#7a9ab0"      # Muted steel blue-gray
COLOR_MILITARY: str = "#c8a840"    # Army gold/khaki
COLOR_SCIENTIST: str = "#ffffff"   # White
COLOR_POLITICIAN: str = "#c070e0"  # Soft violet
COLOR_INFECTED: str = "#ff6600"    # Vivid orange
COLOR_DEAD: str = "#303030"        # Near black
COLOR_EMPTY: str = "#061828"       # Deep ocean background

# ---------------------------------------------------------------------------
# Combat parameters
# ---------------------------------------------------------------------------
FORCE_MILITARY_BONUS: int = 15
FORCE_FLEE_THRESHOLD: int = 60  # Above this value Military does not flee
AGE_PENALTY_THRESHOLD: int = 60 # From this age onward force decays

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DB_PATH: str = "simulations.db"

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
WINDOW_WIDTH: int = 1420
WINDOW_HEIGHT: int = 760
CANVAS_SIZE: int = 700        # Grid canvas size in pixels
UI_REFRESH_MS: int = 80       # Milliseconds between UI refreshes

# ---------------------------------------------------------------------------
# National alert / White House mechanic
# ---------------------------------------------------------------------------
# Delays are in real-world SECONDS (independent of simulation speed).
# Formula: delay = max(MIN_ALERT_DELAY_S, BASE - K * num_panicking)
# The more people in panic when the politician sends the alert,
# the faster the message reaches the White House.
WHITEHOUSE_DELAY_BASE_S: float = 20.0  # Base seconds until the message arrives
WHITEHOUSE_DELAY_K_S: float = 0.15     # Second reduction per panicking person
MIN_ALERT_DELAY_S: float = 6.0         # Minimum wait seconds (bureaucracy is always there)

# ---------------------------------------------------------------------------
# Available strategies
# ---------------------------------------------------------------------------
STRATEGIES: list[str] = ["random", "flee", "group", "military_first"]

# Narrative descriptions of each strategy (for the EventLog)
STRATEGY_DESCRIPTIONS: dict = {
    "flee":           "🏃 EVACUATION Protocol — run and scatter",
    "group":          "👥 GROUPING Protocol — stick together, strength in numbers",
    "military_first": "🎖 MILITARY OFFENSIVE Protocol — soldiers to the front, civilians to shelters",
    "random":         "❓ Protocol... none. The government couldn't agree on anything",
}
