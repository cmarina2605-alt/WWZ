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
GRID_SIZE: int = 250          # Side of the square grid (cells) — was 100

# ---------------------------------------------------------------------------
# Initial population
# ---------------------------------------------------------------------------
NUM_HUMANS: int = 300         # Number of humans at the start (scaled for 250×250)
NUM_ZOMBIES: int = 5          # Number of zombies at the start
NUM_SCIENTISTS: int = 15      # DB default (engine calculates ~10% of NUM_HUMANS)
NUM_MILITARY: int = 20        # DB default (engine calculates ~20% of NUM_HUMANS)
NUM_POLITICIANS: int = 3      # DB default (engine calculates ~5% of NUM_HUMANS)

# ---------------------------------------------------------------------------
# Key locations on the US map (x=west-east, y=north-south, grid 0-249)
# ---------------------------------------------------------------------------
OUTBREAK_POS: tuple = (12, 185)      # San Diego, CA — outbreak origin (José)
LAB_POS: tuple = (170, 155)         # CDC Atlanta, GA — science base
LAB_RADIUS: int = 7                 # Laboratory detection radius (cells)
WHITEHOUSE_POS: tuple = (200, 100)  # Washington D.C. — White House
MILITARY_BASE_POS: tuple = (190, 138) # Fort Bragg, NC — military base
MILITARY_BASE_RADIUS: int = 10      # Radius of the safe zone around the base (cells)
REFUGE_MAX_TICKS: int = 150          # Max ticks a human can stay sheltered before eviction
REFUGE_COOLDOWN_TICKS: int = 200     # Ticks before the same human can re-enter the refuge

# ---------------------------------------------------------------------------
# Continental U.S. polygon for the land mask (grid coords 0-249)
# Used by World to block movement through ocean cells.
# ---------------------------------------------------------------------------
USA_POLYGON: list = [
    # ── Pacific Northwest (Washington State) ──
    (7, 15), (10, 12), (14, 10), (18, 8), (22, 7),
    # ── Northern border (Montana, N. Dakota, Minnesota) ──
    (28, 6), (35, 5), (42, 5), (50, 5), (58, 5), (66, 5),
    (74, 5), (82, 5), (90, 5), (98, 5), (106, 5),
    # ── Great Lakes region (Wisconsin, Michigan) ──
    (114, 5), (122, 5), (130, 6), (138, 7), (144, 10),
    (148, 14), (150, 18), (148, 22),
    # ── Upper New England (Vermont, New Hampshire, Maine) ──
    (152, 16), (156, 14), (160, 12), (166, 10), (172, 8),
    (178, 6), (185, 5), (192, 6), (198, 8),
    # ── Maine coast ──
    (205, 10), (210, 14), (215, 12), (220, 15), (224, 18),
    (228, 22), (230, 26),
    # ── Northeast coast (Massachusetts, Connecticut, New York) ──
    (232, 30), (233, 35), (232, 40), (230, 45),
    (232, 48), (234, 44), (233, 40),
    # ── Mid-Atlantic (New Jersey, Delaware, Maryland) ──
    (230, 52), (228, 56), (230, 60), (228, 64),
    (226, 68), (224, 72), (222, 76),
    # ── Virginia, Carolinas coast ──
    (220, 80), (222, 84), (224, 88), (222, 92),
    (218, 96), (215, 100), (212, 104),
    # ── South Carolina, Georgia coast ──
    (210, 108), (208, 112), (206, 116), (204, 120),
    (202, 124), (200, 130), (198, 136),
    # ── Florida Peninsula (east coast) ──
    (196, 142), (194, 148), (192, 154), (190, 160),
    (188, 166), (185, 172), (182, 180), (178, 188),
    (175, 195), (172, 202), (170, 210),
    # ── Florida tip and Keys ──
    (168, 218), (170, 224), (172, 230), (175, 236),
    (178, 238), (182, 236), (185, 230),
    # ── Florida Peninsula (west coast going north) ──
    (188, 222), (190, 214), (190, 206), (188, 198),
    (186, 192), (184, 186),
    # ── Gulf coast (Florida panhandle) ──
    (180, 182), (176, 186), (172, 188), (168, 190),
    (164, 192), (160, 194), (156, 196),
    # ── Gulf coast (Alabama, Mississippi, Louisiana) ──
    (152, 198), (148, 200), (144, 202), (140, 204),
    (136, 206), (132, 208), (128, 210),
    # ── Louisiana delta ──
    (124, 212), (120, 214), (116, 216), (112, 214),
    (108, 212), (104, 210),
    # ── Texas Gulf coast ──
    (100, 212), (96, 214), (92, 216), (88, 218),
    (84, 220), (80, 222), (76, 224),
    # ── South Texas / Mexico border ──
    (72, 222), (68, 218), (64, 212), (60, 206),
    (56, 200), (52, 195), (48, 190),
    # ── Texas–Mexico border (Rio Grande) ──
    (44, 186), (40, 182), (36, 178), (32, 174),
    (28, 172), (24, 175), (20, 178),
    # ── New Mexico / Arizona border ──
    (16, 182), (12, 186), (8, 190), (6, 194),
    (5, 196), (7, 195),
    # ── Southwest corner (California border) ──
    (8, 192), (6, 188), (5, 184), (5, 180),
    # ── California coast going north ──
    (4, 176), (4, 170), (5, 164), (5, 158),
    (4, 152), (4, 146), (5, 140), (5, 134),
    (4, 128), (5, 122), (5, 116), (5, 110),
    # ── Northern California ──
    (5, 104), (5, 98), (5, 92), (5, 86),
    (5, 80), (5, 74), (5, 68),
    # ── Oregon coast ──
    (5, 62), (5, 56), (5, 50), (5, 44),
    (5, 38), (5, 32),
    # ── Washington coast back to start ──
    (5, 26), (5, 22), (6, 18), (7, 15),
]

# ---------------------------------------------------------------------------
# Geographic map colors (UI)
# ---------------------------------------------------------------------------
OCEAN_COLOR: str = "#061828"        # Deep ocean background
LAND_COLOR: str = "#1c3318"         # Dark terrain green
LAND_BORDER_COLOR: str = "#2e5a28"  # Slightly lighter border
STATE_LINE_COLOR: str = "#2a4e24"   # Subtle state divisions

# ---------------------------------------------------------------------------
# Probability parameters
# ---------------------------------------------------------------------------
P_INFECT: float = 0.25        # Infection probability in an encounter (was 0.40)
P_KILL_ZOMBIE: float = 0.08   # Probability that a human kills the zombie (was 0.05)
P_ESCAPE: float = 0.35        # Base escape probability (was 0.20)

# ---------------------------------------------------------------------------
# Vision / detection range (in cells)
# ---------------------------------------------------------------------------
VISION_HUMAN: int = 25        # Human vision radius (scaled for 250×250)
VISION_ZOMBIE: int = 38       # Zombie vision radius (scaled for 250×250)

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
COLOR_PRESIDENT: str = "#ffd700"   # Gold — the Commander-in-Chief
COLOR_INFECTED: str = "#ff6600"    # Vivid orange
COLOR_DEAD: str = "#303030"        # Near black
COLOR_EMPTY: str = "#061828"       # Deep ocean background

# ---------------------------------------------------------------------------
# Survival attributes (food, water)
# ---------------------------------------------------------------------------
INITIAL_FOOD: int = 100          # Starting food level (0-100)
INITIAL_WATER: int = 100         # Starting water level (0-100)
FOOD_DECAY_PER_TICK: float = 0.15   # Food consumed per tick
WATER_DECAY_PER_TICK: float = 0.20  # Water consumed per tick (dehydration is faster)
STARVATION_THRESHOLD: int = 0    # At this level, agent starts losing force
DEHYDRATION_THRESHOLD: int = 0   # At this level, agent starts losing force
FORCE_LOSS_NO_FOOD: float = 0.3  # Force lost per tick when starving
FORCE_LOSS_NO_WATER: float = 0.5 # Force lost per tick when dehydrated
DEATH_FORCE_THRESHOLD: int = 5   # Below this force from starvation/dehydration → death
REFUGE_FOOD_REGEN: float = 2.0   # Food recovered per tick while in refuge
REFUGE_WATER_REGEN: float = 2.0  # Water recovered per tick while in refuge
MILITARY_AMMO_RESUPPLY: int = 5  # Ammo given to military at the base per visit

# ---------------------------------------------------------------------------
# Combat parameters
# ---------------------------------------------------------------------------
FORCE_MILITARY_BONUS: int = 15
FORCE_FLEE_THRESHOLD: int = 60  # Above this value Military does not flee
AGE_PENALTY_THRESHOLD: int = 60 # From this age onward force decays

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
import os as _os
DB_PATH: str = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "simulations.db")

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
WINDOW_WIDTH: int = 1520
WINDOW_HEIGHT: int = 860
CANVAS_SIZE: int = 800        # Grid canvas size in pixels
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
