"""
main.py — Punto de entrada de la simulación Guerra Mundial J.

Soporta dos modos de ejecución:
    - UI (por defecto): Lanza la interfaz gráfica Tkinter.
    - Batch (--no-ui):  Ejecuta N simulaciones y guarda resultados en DB.

Uso:
    python main.py                          # UI interactiva
    python main.py --no-ui                  # Una simulación sin UI
    python main.py --no-ui --batch 100      # 100 simulaciones batch
    python main.py --seed 42                # Semilla fija con UI
    python main.py --no-ui --seed 42 --batch 10
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
    Parsea los argumentos de línea de comandos.

    Returns:
        Namespace con los argumentos parseados.
    """
    parser = argparse.ArgumentParser(
        description="Guerra Mundial J — Simulación multithread Humanos vs Zombis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
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
        help="Ejecutar en modo batch sin interfaz gráfica.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semilla aleatoria para reproducibilidad.",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=1,
        help="Número de simulaciones a ejecutar en modo batch (default: 1).",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="flee",
        choices=config.STRATEGIES,
        help=f"Estrategia de comportamiento humano. Opciones: {config.STRATEGIES}",
    )
    parser.add_argument(
        "--p-infect",
        type=float,
        default=config.P_INFECT,
        help=f"Probabilidad de infección (default: {config.P_INFECT}).",
    )
    parser.add_argument(
        "--humans",
        type=int,
        default=config.NUM_HUMANS,
        help=f"Número de humanos iniciales (default: {config.NUM_HUMANS}).",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="Mostrar resumen estadístico de simulaciones previas y salir.",
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
    Ejecuta N simulaciones en modo batch y guarda resultados en la DB.

    Args:
        n: Número de simulaciones a ejecutar.
        seed: Semilla base (None = aleatoria). Si se proporciona,
              se incrementa en 1 para cada simulación.
        strategy: Estrategia de comportamiento humano.
        p_infect: Probabilidad de infección.
        n_humans: Número inicial de humanos.
    """
    db = Database()
    print(f"\n[Batch] Iniciando {n} simulaciones | strategy={strategy} | p_infect={p_infect}")
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

        # Esperar a que termine (máx. 120 segundos por simulación)
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
    Lanza la simulación con interfaz gráfica Tkinter.

    Args:
        seed: Semilla aleatoria (None = aleatoria).
        strategy: Estrategia de comportamiento humano.
        p_infect: Probabilidad de infección.
        n_humans: Número inicial de humanos.
    """
    try:
        import tkinter as tk
        # Verificar que Tkinter funciona antes de importar App
        test_root = tk.Tk()
        test_root.destroy()
    except Exception as exc:
        print(f"[Error] No se puede iniciar la UI Tkinter: {exc}")
        print("  Usa --no-ui para el modo batch.")
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
    Función principal: parsea argumentos y lanza el modo correspondiente.
    """
    args = parse_args()

    # Modo estadísticas
    if args.stats:
        db = Database()
        print_summary(db)
        db.close()
        return

    # Aplicar parámetros de CLI a config
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
