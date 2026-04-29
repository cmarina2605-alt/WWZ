# Guerra Mundial J — Complete Study Guide

Everything you need to know for Q&A. Read this the night before.

---

## 1. THE BIG PICTURE

Guerra Mundial J is a **multithreaded zombie apocalypse simulation** set in the continental United States. 305 agents (250 citizens, 20 scientists, 20 military, 10 politicians, 5 zombies) each run as their own Python thread. The simulation explores which survival strategy leads to the best outcomes across hundreds of randomized runs.

**Why threads and not processes?** Because agents share a grid (the world map). Threads share memory natively, so all 305 agents can read/write the same `World.grid` dictionary without serialization. We use `threading.Lock` to prevent corruption. Processes would require IPC (pipes, shared memory), which adds complexity.

**Why not asyncio?** Our agents are CPU-bound (distance calculations, probability math) and need true concurrency for the simulation to feel realistic. `asyncio` is for I/O-bound tasks. Though Python's GIL means only one thread runs Python code at a time, the constant `sleep()` calls between ticks yield the GIL frequently, giving all threads fair scheduling.

---

## 2. CLASS HIERARCHY

```
threading.Thread
  └── Agent (ABC)          ← abstract, defines run() + abstract update()
        ├── Human           ← base human with food/water/fear/empathy
        │     ├── Normal    ← ordinary citizen, no special behavior
        │     ├── Scientist ← moves to CDC, works on antidote
        │     ├── Military  ← hunts zombies, uses ammo, resupplies at Fort Bragg
        │     └── Politician← competes for influence, issues national alerts
        └── Zombie          ← chases humans, infects, gets faster when hungry
```

**Why this hierarchy?** Every agent IS a thread (inherits `threading.Thread`). The `Agent` base class defines the **Template Method pattern** — `run()` is the fixed skeleton:

```python
def run(self):
    while not game_over.is_set():
        pause_event.wait(timeout=0.5)  # blocks if paused
        if game_over.is_set(): break
        self.update()                   # ← abstract, subclasses override
        time.sleep(self.move_delay)
```

Each subclass fills in `update()` with its own behavior. Normal humans flee. Scientists navigate to the CDC. Military hunts zombies. Politicians compete for influence.

---

## 3. THE WORLD (Shared State)

`World` holds the grid as a `dict` mapping `(x, y) -> Agent`. It's a 250x250 grid where only ~30,000 cells are valid land (computed via ray-casting against a US continental polygon at startup and cached).

**Every grid operation acquires `World.lock`:** `place_agent()`, `move_agent()`, `remove_agent()`, `get_state_snapshot()`.

**The "snapshot under lock" pattern:** When we need to read many agents (e.g., finding nearby agents or rendering the UI), we copy the entire grid dict under the lock, then process the copy outside the lock. This keeps the lock held for microseconds instead of milliseconds:

```python
def get_agents_in_radius(self, pos, radius):
    with self.lock:
        snapshot = dict(self.grid)     # brief lock
    # filtering happens outside the lock — no blocking
    return [a for a in snapshot.values() if distance(a.pos, pos) <= radius]
```

**Why a dict and not a 2D array?** Because the grid is sparse — only ~305 agents on 30,000 cells. A dict lookup is O(1) and only stores occupied cells.

---

## 4. PARALLELISM IN DETAIL

### All threads in a running simulation:

| Thread | Count | Purpose | Daemon? |
|--------|-------|---------|---------|
| Main thread | 1 | Tkinter UI mainloop | No |
| Agent threads | ~305+ | Each agent runs its own behavior loop | Yes |
| TickCounter | 1 | Increments `world.tick` at regular intervals | Yes |
| WinChecker | 1 | Checks victory conditions | Yes |
| InfectionMonitor | 1 | Converts infected humans to zombies after 25 ticks | Yes |
| StrategyMonitor | 1 | Waits for national alert, selects strategy | Yes |
| DB-Writer | 1 | Batches event writes to SQLite | Yes |

**Total: ~310-320 threads** (agents + 5 engine threads + DB writer + main).

### Why daemon threads?

All threads except main are daemon threads. When the main thread exits (user closes the window), daemon threads are killed automatically. This prevents zombie threads (pun intended) from keeping the process alive.

### How threads coordinate:

**threading.Event objects** are the primary coordination mechanism. They're like boolean flags that threads can wait on:

| Event | Logic | Purpose |
|-------|-------|---------|
| `game_over` | SET = game ended | All agents check this each loop iteration. When set, every thread exits. |
| `pause_event` | SET = running, CLEAR = paused (inverted!) | Agents call `.wait()`. If cleared, they block. If set, they proceed. |
| `antidote_ready` | SET = antidote delivered | Scientists set this. WinChecker reacts. |
| `national_alert` | SET = emergency declared | Politicians set this. StrategyMonitor reacts. |

**Why Events and not Conditions?** Events are simpler — set once, all waiters wake instantly. We don't need the notify/wait pattern of Conditions because our signals are one-shot (once game_over is set, it stays set).

---

## 5. ALL LOCKS AND WHAT THEY PROTECT

| Lock | What it protects | Why needed |
|------|-----------------|------------|
| `World.lock` | The `grid` dict | 305 agents + engine threads all read/write positions concurrently |
| `World._event_lock` | The `_event_queue` list | UI thread pops events while engine pushes them |
| `Engine._result_lock` | `_end_simulation()` | Prevents double invocation (two threads could detect win simultaneously) |
| `EventBus._lock` | `_subscribers` dict | Multiple threads subscribe/publish |
| `Database._lock` | SQLite `_conn` | SQLite connections aren't thread-safe |
| `CommandHistory._lock` | Command log list | Multiple threads log combat commands |
| `Agent._id_lock` | Atomic ID counter | All agent constructors increment the same counter |

**If asked "why not use RLock?":** We don't need reentrant locking because no function acquires the same lock twice in its call chain. `threading.Lock` is simpler and slightly faster.

**If asked "could you have a deadlock?":** No, because no thread ever holds two locks simultaneously. Deadlock requires a cycle in the lock ordering graph, and we never have Thread A holding Lock 1 waiting for Lock 2 while Thread B holds Lock 2 waiting for Lock 1.

---

## 6. COMBAT SYSTEM

When a human and zombie meet (distance <= 1.5 cells):

1. `combat.resolve_encounter(human, zombie, world)` calculates four probabilities:
   - **p_escape** = `P_ESCAPE * (0.5 + force_ratio * 0.8)`, clamped to [0.08, 0.75]. Higher force ratio (more military nearby) = easier escape.
   - **p_infect** = `P_INFECT` (default 0.25), +0.08 for elderly, reduced by force ratio.
   - **p_human_dies** = `(0.15 - force_ratio * 0.1) * (1 - P_INFECT)`. Low base, further reduced if military present.
   - **p_zombie_dies** = `P_KILL_ZOMBIE` (0.08), +0.25 if military with ammo, +0.05 if military without, -0.02 for civilians.

2. **Normalize** all four to sum to 1.0.

3. **Random roll** (`random.random()`) selects the outcome.

4. The outcome is wrapped in a **Command object** (EscapeCommand, InfectCommand, KillHumanCommand, KillZombieCommand) and executed through `CommandHistory`.

5. The Command's `execute()` applies the effect (state change, removal from grid, EventBus publish).

**If asked "why Command pattern for combat?":** It decouples the probability calculation from the effect application. Commands are logged in CommandHistory, which enables replay, analytics, and debugging. The same pattern handles UI actions (Start, Pause, Reset).

---

## 7. INFECTION / CONVERSION PIPELINE

This is one of the trickiest concurrency challenges in the project:

1. **Combat outcome = "infected":** InfectCommand sets `human.state = "infected"`. The state is "sticky" — `set_state()` rejects any transition from "infected" except to "dead". This prevents the 25-tick incubation from being cancelled.

2. **InfectionMonitor thread** scans all agents periodically. When it first sees an infected agent, it records the tick. After 25 ticks, it calls `convert_infected(human)`.

3. **convert_infected() uses the Prototype pattern** with a two-phase locking strategy:
   - Phase 1 (OUTSIDE lock): `zombie = human.clone()` — creates a new Zombie thread with the human's position. This is expensive (thread initialization), so we do it without holding the lock.
   - Phase 2 (UNDER lock): Remove human from grid, place zombie at same position. This is fast (dict operations).
   - Phase 3: Start the zombie's thread.

**Why two phases?** If we held the lock during `clone()`, all 305 other agents would be blocked from moving for the duration of thread creation. By cloning outside the lock, we minimize lock contention.

**If asked "what if another agent takes the cell during clone?":** `convert_infected()` handles this — if the original cell is occupied, it falls back to finding a nearby free cell.

---

## 8. VISUALIZATION PIPELINE

The UI must never block the simulation, and Tkinter is single-threaded:

1. Every **80ms**, `App._ui_loop()` fires on the main thread.
2. Calls `engine.get_snapshot()` which copies agent state (GIL-safe) and calls `world.get_state_snapshot()` (copies grid under lock, builds info dicts outside lock).
3. `GridCanvas.render()` uses a **pre-allocated pool** of canvas ovals:
   - On first render, creates oval items.
   - On subsequent renders, repositions existing ovals with `coords()` and `itemconfig()`.
   - **Zero create/delete per frame** — this is the key optimization that makes 305+ agents renderable at 12+ FPS.
4. Stats, chart, and event log update from the same snapshot.
5. If result changes, shows a game-over overlay.

**If asked "why not render in a separate thread?":** Tkinter is NOT thread-safe. All widget operations must happen on the main thread. We use `self.after()` to schedule updates. The engine threads never touch Tkinter directly.

---

## 9. DATABASE LAYER

**Architecture:** Singleton Database with two SQLite connections:
- **Main connection** (`_conn`): for reads and synchronous writes (protected by `_lock`).
- **Writer thread connection**: for async batched event inserts via `queue.Queue`.

**Why two connections?** SQLite doesn't allow concurrent writes from the same connection across threads. The writer thread has its own connection and batches up to 50 events per transaction, flushing every 0.5 seconds.

**WAL mode** (Write-Ahead Logging) is enabled, which allows concurrent reads while a write is in progress — critical because the UI reads stats while the engine writes events.

**Schema:**
- `simulations` — stores parameters (seed, strategy, probabilities) and results (duration, final counts).
- `events` — logs every significant action (combat, death, alert) with FK to simulations.

---

## 10. DESIGN PATTERNS (All 6)

| Pattern | Where | Why |
|---------|-------|-----|
| **Template Method** | `Agent.run()` calls abstract `update()` | Every agent type shares the same run loop (check game_over, wait for pause, call update, sleep) but each fills in different behavior |
| **Observer** | `EventBus` (publish/subscribe) | Decouples components. Combat publishes "zombie_killed"; WinChecker subscribes and reacts instantly instead of polling |
| **Singleton** | `SimulationSignals`, `Database` | Exactly one set of game signals and one DB connection, shared across all threads |
| **Command** | `commands.py` (UI + combat actions) | Encapsulates actions as objects for logging and history. Every combat outcome is a Command executed through CommandHistory |
| **Prototype** | `Agent.clone()` in `convert_infected()` | When a human becomes a zombie, we clone the human's state (position, attributes) into a new Zombie object instead of building from scratch |
| **Strategy** | `movement.py` (flee/group/military_first/random) | Movement behavior changes at runtime when the President sets a strategy. Same agent, different behavior — no subclassing needed |

---

## 11. MOVEMENT / STRATEGY SYSTEM

Before the White House responds, all humans use the default "none" strategy (flee from nearby zombies, random walk otherwise).

After a Politician triggers `national_alert` and the StrategyMonitor selects a strategy:

- **"flee"**: Flee vector multiplied 1.5x. Everyone runs aggressively.
- **"group"**: Move toward centroid of nearby humans. Safety in numbers.
- **"military_first"**: Civilians follow closest military. Military gets expanded vision and lower aggression threshold.
- **"random"**: Random walk regardless of threats. Simulates government deadlock/chaos.

**How strategy selection works:** The StrategyMonitor waits for `national_alert`. After a delay proportional to the number of panicking agents (more panic = faster response), it finds the most influential living politician and adopts their `ideology` as the strategy.

**Movement uses Manhattan distance** (|dx| + |dy|) instead of A*/Dijkstra. This is a deliberate trade-off — pathfinding with 305 concurrent agents would be too expensive. Manhattan distance gives "good enough" movement.

---

## 12. BATCH MODE

`python main.py --no-ui --batch 100 --strategy flee`

Runs 100 simulations sequentially with no UI. Each run:
1. Creates a fresh `Engine` with a random seed.
2. Starts all threads.
3. Main thread polls `engine.running` until done (or 120s timeout).
4. Saves results to SQLite.
5. After all runs: prints strategy win rates and sensitivity analysis.

This lets us answer the thesis question statistically: "Which strategy wins most often across hundreds of randomized simulations?"

---

## 13. POTENTIAL QUESTIONS AND ANSWERS

**Q: How do you prevent race conditions on the grid?**
A: Every grid operation (place, move, remove, snapshot) acquires `World.lock`. We use the "snapshot under lock" pattern — copy the grid dict briefly under the lock, then process the copy outside.

**Q: What happens if two agents try to move to the same cell?**
A: `move_agent()` checks if the target cell is occupied under the lock. If it is, the move fails and the agent stays put. No crash, no corruption.

**Q: Why not use multiprocessing instead of threading?**
A: All agents share the `World.grid` dictionary. With multiprocessing, we'd need IPC (shared memory, pipes) to synchronize 305 agents, which adds massive complexity. The GIL limits CPU parallelism, but our agents spend most of their time sleeping between ticks, so the GIL isn't a bottleneck.

**Q: How do you handle the GIL?**
A: Every agent calls `time.sleep(move_delay)` between ticks, which releases the GIL. This gives all 310 threads fair scheduling. The GIL only prevents CPU parallelism, but our workload is mostly wait-bound, not compute-bound.

**Q: Could you have a deadlock?**
A: No. No thread ever holds two locks simultaneously. Deadlock requires a cycle in lock acquisition order, and we never create one.

**Q: What's the hardest concurrency problem you solved?**
A: Infected-to-zombie conversion. A human thread is running while we need to swap it for a zombie. We solved it with a two-phase approach: clone the zombie outside the lock (expensive but non-blocking), then do the atomic grid swap under the lock (fast). The InfectionMonitor thread handles the timing.

**Q: Why threading.Event instead of Condition variables?**
A: Our signals are one-shot broadcasts (e.g., game_over stays set forever once set). Events are simpler and more efficient for this use case. Conditions are for producer/consumer patterns with repeated notify/wait cycles, which we don't need.

**Q: How does the UI not freeze with 305 threads?**
A: The UI runs on the main thread with `self.after(80, _ui_loop)`. It never waits for agents — it just reads a snapshot of the current state every 80ms. The pre-allocated canvas pool means zero widget creation per frame.

**Q: What design pattern is used for combat?**
A: Command pattern. Each combat outcome (escape, infect, kill) is a Command object with an `execute()` method. Commands are logged in CommandHistory for replay and analytics.

**Q: How does the antidote work?**
A: Scientists navigate toward the CDC lab in Atlanta. When inside the lab radius, they increment `antidote_progress` each tick (rate = 1 + intelligence/33). When progress reaches `ANTIDOTE_TICKS` (3000), `antidote_ready` is set. WinChecker detects this and triggers human victory.

**Q: Why SQLite and not PostgreSQL?**
A: The simulation is a standalone desktop app. SQLite requires zero setup, stores everything in one file, and WAL mode gives us the concurrent read/write performance we need. PostgreSQL would add deployment complexity for no benefit.

**Q: How many lines of code?**
A: ~2,500 lines of Python across 25 source files, plus ~800 lines of tests.
