"""
stats.py — Análisis estadístico de los resultados de simulaciones.

Funciones de alto nivel que consultan la base de datos para extraer
conclusiones sobre qué configuraciones favorecen a humanos o zombis.

Funciones principales:
    analyze_strategies(db)
        → Dict {strategy: {total, human_wins, win_rate_pct}}
        Responde: ¿qué estrategia humana tiene mayor tasa de victoria?

    sensitivity_analysis(param, db)
        → List [{value, total, win_rate_pct}]
        Responde: ¿cómo varía el resultado al cambiar p_infect o la visión?
        Parámetros soportados: "p_infect", "vision_zombie", "vision_human".

    print_summary(db)
        Imprime en consola un resumen formateado tras un run en modo batch.
        Muestra: estrategias ordenadas por win_rate, sensibilidad a p_infect.

    get_best_strategy(db)
        → str | None  — nombre de la estrategia con mayor win_rate_pct.

    get_recent_simulations(limit, db)
        → List[Dict]  — las N simulaciones más recientes de la base de datos.

Todas las funciones aceptan db=None y crean una instancia con la ruta
por defecto si no se proporciona, para facilitar el uso desde la CLI.
"""

from typing import Dict, List, Any, Optional

from db.database import Database
from db.models import SELECT_WIN_RATE_BY_STRATEGY, SELECT_SENSITIVITY_P_INFECT


def analyze_strategies(db: Optional[Database] = None) -> Dict[str, Dict[str, Any]]:
    """
    Analiza la tasa de victoria de cada estrategia registrada en la DB.

    Args:
        db: Instancia de Database. Si es None, crea una con la ruta por defecto.

    Returns:
        Dict de {strategy: {"total": int, "human_wins": int, "win_rate_pct": float}}.

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
    Analiza cómo varía el resultado según un parámetro dado.

    Parámetros soportados: "p_infect", "vision_zombie", "vision_human".

    Args:
        param: Nombre del parámetro a analizar.
        db: Instancia de Database. Si es None, usa la ruta por defecto.

    Returns:
        Lista de dicts con {bucket_value, total, win_rate_pct} ordenados
        por el valor del bucket.

    Raises:
        ValueError: Si el parámetro no está soportado.
    """
    supported = {"p_infect", "vision_zombie", "vision_human"}
    if param not in supported:
        raise ValueError(
            f"Parámetro no soportado: '{param}'. Usa uno de: {supported}"
        )

    if db is None:
        db = Database()

    if param == "p_infect":
        query = SELECT_SENSITIVITY_P_INFECT
        bucket_col = "p_infect_bucket"
    else:
        # Construcción dinámica para visión
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
    Imprime un resumen de resultados batch en consola.

    Muestra la tasa de victoria por estrategia y la sensibilidad
    al parámetro p_infect.

    Args:
        db: Instancia de Database. Si es None, usa la ruta por defecto.
    """
    if db is None:
        db = Database()

    total_sims = db.get_simulation_count()
    print(f"\n{'='*60}")
    print(f"  GUERRA MUNDIAL J — Resumen de {total_sims} simulaciones")
    print(f"{'='*60}")

    # Estrategias
    print("\n📊 Tasa de victoria por estrategia:")
    print(f"  {'Estrategia':<20} {'Total':>8} {'Victorias':>10} {'Win %':>8}")
    print(f"  {'-'*50}")
    strategies = analyze_strategies(db)
    for strategy, data in strategies.items():
        print(
            f"  {strategy:<20} {data['total']:>8} {data['human_wins']:>10} "
            f"{data['win_rate_pct']:>7.1f}%"
        )

    # Sensibilidad p_infect
    print("\n🔬 Sensibilidad a p_infect:")
    print(f"  {'p_infect':>10} {'Total':>8} {'Win %':>8}")
    print(f"  {'-'*30}")
    try:
        sensitivity = sensitivity_analysis("p_infect", db)
        for row in sensitivity:
            print(
                f"  {row['value']:>10.1f} {row['total']:>8} {row['win_rate_pct']:>7.1f}%"
            )
    except Exception as exc:
        print(f"  Error al calcular sensibilidad: {exc}")

    print(f"\n{'='*60}\n")


def get_best_strategy(db: Optional[Database] = None) -> Optional[str]:
    """
    Retorna el nombre de la estrategia con mayor tasa de victoria.

    Args:
        db: Instancia de Database.

    Returns:
        Nombre de la mejor estrategia, o None si no hay datos.
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
    Retorna las simulaciones más recientes.

    Args:
        limit: Número máximo de simulaciones a retornar.
        db: Instancia de Database.

    Returns:
        Lista de dicts con los datos de cada simulación.
    """
    if db is None:
        db = Database()

    all_sims = db.get_all_simulations()
    return all_sims[:limit]
