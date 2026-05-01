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
#
# Position constants below are populated by apply_map_version() at module
# load — see the "Map versioning" section at the end of this file. Both v1
# (the original hand-drawn map) and v2 (the lat/lon-projected real shape)
# are defined there so that --seed N runs remain reproducible against the
# historical map.
# ---------------------------------------------------------------------------
OUTBREAK_POS: tuple = (0, 0)         # populated by apply_map_version()
LAB_POS: tuple = (0, 0)              # populated by apply_map_version()
LAB_RADIUS: int = 7                  # Laboratory detection radius (cells; version-independent)
WHITEHOUSE_POS: tuple = (0, 0)       # populated by apply_map_version()
MILITARY_BASE_POS: tuple = (0, 0)    # populated by apply_map_version()
MILITARY_BASE_RADIUS: int = 10       # Radius of the safe zone around the base (cells)
REFUGE_MAX_TICKS: int = 150          # Max ticks a human can stay sheltered before eviction
REFUGE_COOLDOWN_TICKS: int = 200     # Ticks before the same human can re-enter the refuge

# ---------------------------------------------------------------------------
# v1 hand-drawn polygon (continental U.S., grid coords 0-249).
# Preserved verbatim so --map-version v1 reproduces historical seeds.
# The active USA_POLYGON is populated by apply_map_version() below.
# ---------------------------------------------------------------------------
_MAP_V1_POLYGON: list = [
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
# DB_PATH is populated by apply_map_version() — v1 writes to simulations_v1.db,
# v2 writes to simulations.db. See "Map versioning" section at end of file.
DB_PATH: str = ""

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


# ===========================================================================
# Map versioning
# ===========================================================================
# Two versions of the U.S. map ship in this file:
#
#   v1 — the original hand-drawn polygon and city positions. Preserved so
#        old --seed N runs from simulations_v1.db can be re-executed and
#        reproduce their original outcomes.
#
#   v2 — a lat/lon-projected polygon traced from real coordinates: includes
#        the Lake Superior notch, Cape Cod, the Outer Banks, the Florida
#        bulge, the Texas point at Brownsville, and the real California
#        curve. Cities are repositioned to their actual lat/lon. v2 is the
#        default and writes to simulations.db.
#
# Switch versions at runtime with main.py's --map-version flag, which calls
# apply_map_version() before any World/Engine instantiation.
# ===========================================================================

# v1 state-divide decoration (the abstract dashed lines previously hardcoded
# in ui/grid_canvas.py). Kept so the v1 map renders unchanged.
_MAP_V1_STATE_LINES: list = [
    [(38, 8), (36, 30), (35, 60), (35, 100), (35, 140), (35, 180), (35, 195)],
    [(70, 5), (68, 30), (67, 60), (67, 100), (67, 140), (68, 180), (72, 210)],
    [(108, 5), (106, 30), (105, 60), (105, 100), (106, 140), (108, 180), (108, 210)],
    [(165, 8), (168, 30), (170, 60), (172, 80), (175, 100), (180, 120), (185, 140)],
    [(35, 140), (70, 142), (108, 145), (140, 148), (170, 150), (200, 140)],
    [(35, 60), (70, 58), (108, 56), (140, 55), (165, 54)],
]

# v2 polygon — equirectangular projection (lon -125→x=5, lon -66→x=245;
# lat 49→y=5, lat 24→y=240). Roughly 90 points, organized by region.
_MAP_V2_POLYGON: list = [
    # ── NW corner / Olympic Peninsula ──
    (6, 11), (8, 7), (12, 5),
    # ── Northern border (49°N) going east ──
    (25, 5), (45, 5), (65, 5), (85, 5), (105, 5), (120, 5), (127, 5),
    # ── Lake Superior notch (south shore) ──
    (130, 12), (135, 22), (138, 26), (145, 28), (155, 28),
    # ── Sault Ste. Marie / north of Lake Michigan ──
    (162, 30), (168, 32),
    # ── Around Lake Michigan (Lower Peninsula MI) ──
    (173, 38), (175, 50), (173, 62), (170, 72),
    # ── South shore of Lake Erie ──
    (180, 76), (192, 76), (202, 72),
    # ── Lake Ontario / NY northern border ──
    (207, 62), (210, 50),
    # ── NY / Maine — Canada border up ──
    (213, 38), (220, 28), (232, 19),
    # ── Maine east coast ──
    (240, 28), (241, 38), (238, 46), (232, 52), (228, 55),
    # ── Boston / Cape Cod (sticks east) ──
    (224, 60), (228, 68), (230, 73), (226, 75),
    # ── Long Island / NYC ──
    (220, 76), (213, 82),
    # ── New Jersey / Delaware coast ──
    (212, 90), (210, 98),
    # ── Chesapeake Bay (Virginia) ──
    (204, 108), (203, 116),
    # ── NC Outer Banks (Cape Hatteras) ──
    (207, 130),
    # ── NC / SC / GA coast ──
    (197, 144), (188, 156), (184, 165),
    # ── Jacksonville FL ──
    (181, 178),
    # ── Florida east coast (bulges east, the v1 bug fix) ──
    (184, 188), (187, 200), (188, 212), (186, 224), (185, 230),
    # ── Florida Keys (hooks west) ──
    (178, 236), (170, 235),
    # ── Florida west coast going north ──
    (175, 228), (180, 218), (181, 208), (180, 198), (178, 193),
    # ── Panhandle going west ──
    (175, 184), (171, 182), (165, 181), (159, 180), (156, 178),
    # ── Mississippi / Alabama coast ──
    (152, 180), (147, 184),
    # ── Mississippi Delta (sticks south) ──
    (145, 194),
    # ── Louisiana / Texas border ──
    (138, 184), (130, 184),
    # ── Texas Gulf coast going down to Brownsville ──
    (125, 186), (122, 190), (117, 204),
    # ── Brownsville (south tip of Texas) ──
    (119, 222),
    # ── Rio Grande going west to El Paso ──
    (110, 210), (100, 196), (90, 180), (80, 168),
    # ── NM/AZ–Mexico border ──
    (60, 168), (45, 168),
    # ── Tijuana / SoCal–Mexico border ──
    (37, 160),
    # ── Southern California coast going north ──
    (33, 146), (28, 138), (23, 130), (18, 122),
    # ── San Francisco Bay ──
    (15, 110),
    # ── Cape Mendocino ──
    (10, 95),
    # ── Oregon coast ──
    (8, 75), (7, 55),
    # ── Washington coast / closing back to start ──
    (8, 35), (6, 15),
]

# v2 state-divide lines: a mix of major rivers, ranges, and state borders.
# Each entry is a polyline drawn as a dashed stroke by GridCanvas.
_MAP_V2_STATE_LINES: list = [
    # Mississippi River (Lake Itasca → delta)
    [(140, 28), (138, 55), (135, 85), (133, 120), (135, 155), (140, 175), (145, 194)],
    # Continental Divide (Rockies, approximation)
    [(40, 15), (43, 45), (48, 85), (53, 125), (60, 160)],
    # Appalachian backbone
    [(205, 38), (200, 70), (192, 105), (185, 140)],
    # Texas northern border (panhandle)
    [(75, 170), (130, 170)],
    # KS/NE / IA/MO line (~40°N)
    [(95, 135), (160, 135)],
    # ND/SD / MN dividing line (~46°N)
    [(95, 80), (162, 80)],
    # Mason-Dixon line (PA/MD)
    [(168, 95), (210, 95)],
    # CA-NV vertical
    [(45, 90), (45, 140)],
    # MN-Canada notch (Lake of the Woods area)
    [(125, 5), (130, 28)],
]

# v2 context cities — decorative only. Rendered as small gray markers by
# GridCanvas to give the audience visual anchors. Not consumed by the
# simulation logic anywhere.
_MAP_V2_CONTEXT_CITIES: list = [
    {"name": "NYC",     "pos": (210, 84),  "color": "#9aa6b3"},
    {"name": "LA",      "pos": (35, 146),  "color": "#9aa6b3"},
    {"name": "Chicago", "pos": (157, 72),  "color": "#9aa6b3"},
    {"name": "Houston", "pos": (123, 185), "color": "#9aa6b3"},
    {"name": "Miami",   "pos": (185, 223), "color": "#9aa6b3"},
    {"name": "Seattle", "pos": (16, 18),   "color": "#9aa6b3"},
    {"name": "Denver",  "pos": (86, 92),   "color": "#9aa6b3"},
    {"name": "Dallas",  "pos": (120, 157), "color": "#9aa6b3"},
]

import os as _os
_MAP_DIR = _os.path.dirname(_os.path.abspath(__file__))

# Single source of truth for per-version map data. apply_map_version() copies
# values from here into the module-level constants the rest of the codebase
# reads (USA_POLYGON, OUTBREAK_POS, etc.).
MAP_DATA: dict = {
    "v1": {
        "polygon":           _MAP_V1_POLYGON,
        "outbreak_pos":      (12, 185),    # San Diego (original placement)
        "lab_pos":           (170, 155),   # CDC Atlanta (original)
        "whitehouse_pos":    (200, 100),   # Washington D.C. (original)
        "military_base_pos": (190, 138),   # Fort Bragg (original)
        "state_lines":       _MAP_V1_STATE_LINES,
        "context_cities":    [],
        "db_path":           _os.path.join(_MAP_DIR, "simulations_v1.db"),
    },
    "v2": {
        "polygon":           _MAP_V2_POLYGON,
        "outbreak_pos":      (40, 158),    # San Diego (lat/lon-projected, +5 inland)
        "lab_pos":           (170, 149),   # CDC Atlanta (lat/lon-projected)
        "whitehouse_pos":    (200, 100),   # Washington D.C. (already correct)
        "military_base_pos": (192, 136),   # Fort Bragg (lat/lon-projected)
        "state_lines":       _MAP_V2_STATE_LINES,
        "context_cities":    _MAP_V2_CONTEXT_CITIES,
        "db_path":           _os.path.join(_MAP_DIR, "simulations.db"),
    },
}

# Module-level constants populated by apply_map_version().
# Other modules read these via `config.X` — they MUST exist before that
# read happens. apply_map_version(MAP_VERSION) at the bottom of this file
# fills them with the default v2 values during initial import.
USA_POLYGON: list = []
STATE_LINES: list = []
CONTEXT_CITIES: list = []
MAP_VERSION: str = "v2"


def apply_map_version(version: str) -> None:
    """
    Switch the active map version.

    Must be called before any World or Engine is instantiated, otherwise
    the precomputed land mask in World._land_cache and any engine state
    will be tied to the previously active polygon.

    Side effect: rebinds the module-level constants USA_POLYGON, OUTBREAK_POS,
    LAB_POS, WHITEHOUSE_POS, MILITARY_BASE_POS, STATE_LINES, CONTEXT_CITIES,
    and DB_PATH so that `config.<NAME>` everywhere returns the new values.

    Args:
        version: "v1" or "v2".

    Raises:
        ValueError: if `version` is not a known map version.
    """
    global MAP_VERSION, USA_POLYGON, OUTBREAK_POS, LAB_POS
    global WHITEHOUSE_POS, MILITARY_BASE_POS, STATE_LINES, CONTEXT_CITIES, DB_PATH

    if version not in MAP_DATA:
        raise ValueError(
            f"Unknown map version {version!r}; options: {list(MAP_DATA)}"
        )

    MAP_VERSION       = version
    data              = MAP_DATA[version]
    USA_POLYGON       = data["polygon"]
    OUTBREAK_POS      = data["outbreak_pos"]
    LAB_POS           = data["lab_pos"]
    WHITEHOUSE_POS    = data["whitehouse_pos"]
    MILITARY_BASE_POS = data["military_base_pos"]
    STATE_LINES       = data["state_lines"]
    CONTEXT_CITIES    = data["context_cities"]
    DB_PATH           = data["db_path"]


# Initialize from default version (v2). Other modules importing config.py
# after this point see the v2 polygon and city positions.
apply_map_version(MAP_VERSION)
