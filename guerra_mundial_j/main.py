"""
main.py — Entry point for the Guerra Mundial J simulation.

This file is the only one that should be executed directly. It parses
command-line arguments and launches one of two modes:

UI Mode (default):
    Launches the Tkinter graphical interface. The user can start, pause
    and restart the simulation, adjust parameters with sliders and observe
    the grid in real time alongside the event log and statistics.

Batch Mode (--no-ui):
    Runs N simulations without a graphical interface and saves the results
    to simulations.db for later analysis with --stats.

Available arguments:
    --no-ui              Headless mode (no Tkinter window).
    --seed INT           Random seed for reproducibility.
    --batch INT          Number of simulations in batch mode (default: 1).
    --strategy STR       Human strategy: flee | group | military_first | random.
    --p-infect FLOAT     Infection probability in encounters (0.0–1.0).
    --humans INT         Number of humans at the start of the simulation.
    --stats              Display statistical summary from the DB and exit.

Examples:
    python main.py
    python main.py --no-ui --batch 50
    python main.py --seed 12345
    python main.py --no-ui --seed 42 --strategy military_first
    python main.py --stats
"""

import argparse
import sys
import time
import random

import config
from simulation.engine import Engine
from db.database import Database
from db.stats import print_summary


def parse_args() -> argparse.Namespace:
    """
    Parses command-line arguments.

    Returns:
        Namespace with the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Guerra Mundial J — Multithreaded Humans vs Zombies Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --no-ui --batch 50
  python main.py --seed 12345
  python main.py --no-ui --seed 42 --strategy military_first
        """,
    )

    parser.add_argument(
        "--no-ui",
        action="store_true",
        default=False,
        help="Run in batch mode without a graphical interface.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=1,
        help="Number of simulations to run in batch mode (default: 1).",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="flee",
        choices=config.STRATEGIES,
        help=f"Human behavior strategy. Options: {config.STRATEGIES}",
    )
    parser.add_argument(
        "--p-infect",
        type=float,
        default=config.P_INFECT,
        help=f"Infection probability (default: {config.P_INFECT}).",
    )
    parser.add_argument(
        "--humans",
        type=int,
        default=config.NUM_HUMANS,
        help=f"Initial number of humans (default: {config.NUM_HUMANS}).",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="Display statistical summary of previous simulations and exit.",
    )

    return parser.parse_args()


def run_batch(
    n: int,
    seed: int | None,
    strategy: str,
    p_infect: float,
    n_humans: int,
) -> None:
    """
    Runs N simulations in batch mode and saves results to the DB.

    Args:
        n: Number of simulations to run.
        seed: Base seed (None = random). If provided,
              it is incremented by 1 for each simulation.
        strategy: Human behavior strategy.
        p_infect: Infection probability.
        n_humans: Initial number of humans.
    """
    db = Database()
    print(f"\n[Batch] Starting {n} simulations | strategy={strategy} | p_infect={p_infect}")
    print("-" * 60)

    for i in range(n):
        current_seed = (seed + i) if seed is not None else None
        engine = Engine(
            seed=current_seed,
            strategy=strategy,
            n_humans=n_humans,
            p_infect=p_infect,
        )
        engine.start_simulation()

        # Wait for it to finish (max. 120 seconds per simulation)
        timeout = 120.0
        start_t = time.time()
        while engine.running and (time.time() - start_t) < timeout:
            time.sleep(0.2)

        if engine.running:
            engine.stop()

        stats = engine.get_stats()
        sim_id = db.save_simulation({
            "seed": stats["seed"],
            "p_infect": stats["p_infect"],
            "strategy": stats["strategy"],
            "result": stats["result"],
            "duration": stats["duration"],
            "humans_final": stats["n_humans"],
            "zombies_final": stats["n_zombies"],
            "tick_final": stats["tick"],
        })

        print(
            f"  [{i+1:>4}/{n}] seed={stats['seed']:<8} "
            f"result={stats.get('result','?'):<12} "
            f"ticks={stats['tick']:<6} "
            f"duration={stats['duration']:.1f}s"
        )

    print("-" * 60)
    print_summary(db)
    db.close()


def run_ui(seed: int | None, strategy: str, p_infect: float, n_humans: int) -> None:
    """
    Launches the simulation with the Tkinter graphical interface.

    Args:
        seed: Random seed (None = random).
        strategy: Human behavior strategy.
        p_infect: Infection probability.
        n_humans: Initial number of humans.
    """
    try:
        import tkinter as tk
        # Verify that Tkinter works before importing App
        test_root = tk.Tk()
        test_root.destroy()
    except Exception as exc:
        print(f"[Error] Cannot start the Tkinter UI: {exc}")
        print("  Use --no-ui for batch mode.")
        sys.exit(1)

    from ui.app import App

    engine = Engine(
        seed=seed,
        strategy=strategy,
        n_humans=n_humans,
        p_infect=p_infect,
    )
    app = App(engine)
    app.mainloop()


def main() -> None:
    """
    Main function: parses arguments and launches the corresponding mode.
    """
    args = parse_args()

    # Statistics mode
    if args.stats:
        db = Database()
        print_summary(db)
        db.close()
        return

    # Apply CLI parameters to config
    config.P_INFECT = args.p_infect
    config.NUM_HUMANS = args.humans

    if args.no_ui:
        run_batch(
            n=args.batch,
            seed=args.seed,
            strategy=args.strategy,
            p_infect=args.p_infect,
            n_humans=args.humans,
        )
    else:
        run_ui(
            seed=args.seed,
            strategy=args.strategy,
            p_infect=args.p_infect,
            n_humans=args.humans,
        )


if __name__ == "__main__":
    main()
