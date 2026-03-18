"""
stats.py — Statistical analysis of simulation results.

High-level functions that query the database to draw conclusions about
which configurations favor humans or zombies.

Main functions:
    analyze_strategies(db)
        → Dict {strategy: {total, human_wins, win_rate_pct}}
        Answers: which human strategy has the highest win rate?

    sensitivity_analysis(param, db)
        → List [{value, total, win_rate_pct}]
        Answers: how does the result vary when changing p_infect or vision?
        Supported parameters: "p_infect", "vision_zombie", "vision_human".

    print_summary(db)
        Prints a formatted summary to the console after a batch run.
        Shows: strategies sorted by win_rate, sensitivity to p_infect.

    get_best_strategy(db)
        → str | None  — name of the strategy with the highest win_rate_pct.

    get_recent_simulations(limit, db)
        → List[Dict]  — the N most recent simulations from the database.

All functions accept db=None and create an instance with the default path
if not provided, to facilitate use from the CLI.
"""

from typing import Dict, List, Any, Optional

from db.database import Database
from db.models import SELECT_WIN_RATE_BY_STRATEGY, SELECT_SENSITIVITY_P_INFECT


def analyze_strategies(db: Optional[Database] = None) -> Dict[str, Dict[str, Any]]:
    """
    Analyzes the win rate of each strategy registered in the DB.

    Args:
        db: Database instance. If None, creates one with the default path.

    Returns:
        Dict of {strategy: {"total": int, "human_wins": int, "win_rate_pct": float}}.

    Example:
        >>> results = analyze_strategies()
        >>> print(results["flee"]["win_rate_pct"])
        42.5
    """
    if db is None:
        db = Database()

    with db._lock:
        cursor = db._conn.execute(SELECT_WIN_RATE_BY_STRATEGY)
        rows = cursor.fetchall()

    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        strategy = row["strategy"]
        result[strategy] = {
            "total": row["total"],
            "human_wins": row["human_wins"],
            "win_rate_pct": row["win_rate_pct"],
        }
    return result


def sensitivity_analysis(
    param: str,
    db: Optional[Database] = None,
) -> List[Dict[str, Any]]:
    """
    Analyzes how the result varies according to a given parameter.

    Supported parameters: "p_infect", "vision_zombie", "vision_human".

    Args:
        param: Name of the parameter to analyze.
        db: Database instance. If None, uses the default path.

    Returns:
        List of dicts with {bucket_value, total, win_rate_pct} ordered
        by the bucket value.

    Raises:
        ValueError: If the parameter is not supported.
    """
    supported = {"p_infect", "vision_zombie", "vision_human"}
    if param not in supported:
        raise ValueError(
            f"Unsupported parameter: '{param}'. Use one of: {supported}"
        )

    if db is None:
        db = Database()

    if param == "p_infect":
        query = SELECT_SENSITIVITY_P_INFECT
        bucket_col = "p_infect_bucket"
    else:
        # Dynamic construction for vision
        query = f"""
            SELECT
                {param} AS bucket,
                COUNT(*) AS total,
                ROUND(
                    100.0 * SUM(CASE WHEN result = 'humans_win' THEN 1 ELSE 0 END)
                    / COUNT(*), 2
                ) AS win_rate_pct
            FROM simulations
            WHERE result IS NOT NULL
            GROUP BY {param}
            ORDER BY {param}
        """
        bucket_col = "bucket"

    with db._lock:
        cursor = db._conn.execute(query)
        rows = cursor.fetchall()

    return [
        {
            "value": row[bucket_col],
            "total": row["total"],
            "win_rate_pct": row["win_rate_pct"],
        }
        for row in rows
    ]


def print_summary(db: Optional[Database] = None) -> None:
    """
    Prints a batch results summary to the console.

    Shows the win rate by strategy and sensitivity to p_infect.

    Args:
        db: Database instance. If None, uses the default path.
    """
    if db is None:
        db = Database()

    total_sims = db.get_simulation_count()
    print(f"\n{'='*60}")
    print(f"  GUERRA MUNDIAL J — Summary of {total_sims} simulations")
    print(f"{'='*60}")

    # Strategies
    print("\n📊 Win rate by strategy:")
    print(f"  {'Strategy':<20} {'Total':>8} {'Wins':>10} {'Win %':>8}")
    print(f"  {'-'*50}")
    strategies = analyze_strategies(db)
    for strategy, data in strategies.items():
        print(
            f"  {strategy:<20} {data['total']:>8} {data['human_wins']:>10} "
            f"{data['win_rate_pct']:>7.1f}%"
        )

    # p_infect sensitivity
    print("\n🔬 Sensitivity to p_infect:")
    print(f"  {'p_infect':>10} {'Total':>8} {'Win %':>8}")
    print(f"  {'-'*30}")
    try:
        sensitivity = sensitivity_analysis("p_infect", db)
        for row in sensitivity:
            print(
                f"  {row['value']:>10.1f} {row['total']:>8} {row['win_rate_pct']:>7.1f}%"
            )
    except Exception as exc:
        print(f"  Error calculating sensitivity: {exc}")

    print(f"\n{'='*60}\n")


def get_best_strategy(db: Optional[Database] = None) -> Optional[str]:
    """
    Returns the name of the strategy with the highest win rate.

    Args:
        db: Database instance.

    Returns:
        Name of the best strategy, or None if there is no data.
    """
    strategies = analyze_strategies(db)
    if not strategies:
        return None
    return max(strategies, key=lambda s: strategies[s]["win_rate_pct"])


def get_recent_simulations(
    limit: int = 10,
    db: Optional[Database] = None,
) -> List[Dict[str, Any]]:
    """
    Returns the most recent simulations.

    Args:
        limit: Maximum number of simulations to return.
        db: Database instance.

    Returns:
        List of dicts with each simulation's data.
    """
    if db is None:
        db = Database()

    all_sims = db.get_all_simulations()
    return all_sims[:limit]
