# Guerra Mundial J — Speaker Script

Each section = one slide. The slides are visual-first with minimal text — you explain everything verbally.

---

## Slide 1 — GUERRA MUNDIAL J

> "Hello everyone. Our project is called **Guerra Mundial J** — a multithreaded survival simulation inspired by World War Z. Humans versus zombies in a full-scale apocalypse."

---

## Slide 2 — Thesis

> "The goal is to simulate a zombie apocalypse using **random interactions** and **parallel computing**. The core question: which **strategy** chosen by the president leads to better **long-term survival**? We don't just run one game — we run hundreds of simulations and analyze the data statistically."

---

## Slide 3 — World and Resources

> "The world is a **250 by 250 grid** mapped to the continental United States using a ray-casting polygon mask — about **30,000 walkable land cells**. There are 4 key locations: **San Diego** where the outbreak starts, the **CDC Lab in Atlanta** where scientists work on the antidote, **Fort Bragg** as the military base, and the **White House** where the strategy gets set."

---

## Slide 4 — Roles

> "There are **305 agents**, each running as its own thread. **250 Normal citizens** who survive and flee. **20 Scientists** working on the antidote. **20 Military** soldiers who hunt zombies. **10 Politicians** who compete for influence — the most influential becomes President. And **5 Zombies** that spread the infection. 305 agents equals 305 concurrent threads."

---

## Slide 5 — Infection lifecycle

> "The simulation runs through 5 phases. **Outbreak** — Jose creates Formula Z and zombies appear. **Panic** — fear cascades through nearby agents. **Alert** — a politician detects zombies and triggers a national response. **Response** — the President sets the survival strategy. And **Resolution** — either the antidote is delivered, or humanity goes extinct."

---

## Slide 6 — Strategies

> "The President imposes one of 4 strategies. **Flee** — aggressive escape, everyone runs. **Group** — safety in numbers, agents cluster together. **Military First** — soldiers actively hunt zombies. And **Random** — total chaos, no coordination. Each strategy dramatically changes the outcome, which is what we analyze in batch mode."

---

## Slide 7 — Combat

> "When a human encounters a zombie, combat resolves based on **probability**, **force ratio**, and **randomness**. **Escape** at 35% base rate, modified by force ratio. **Infection** at 25% — 25-tick incubation then conversion. **Human dies** at 15% — instant death. **Zombie dies** at 8%, with a 25% bonus if the military has ammo. Probabilities are normalized and a random roll decides."

---

## Slide 8 — End conditions

> "There are two possible outcomes. **Humans win** if scientists deliver the antidote to the White House or all zombies are eliminated. **Zombies win** if all humans are dead or infected, if the simulation times out with no antidote, or if there are no living scientists left."

---

## Slide 9 — Structure (OOP)

> "The class hierarchy starts from Python's `threading.Thread`. Our abstract **Agent** class extends it and defines the `run()` method, which calls `update()` in a loop — this is the **Template Method** pattern. **Human** and **Zombie** branch from Agent. Human has four subclasses: Normal, Scientist, Military, Politician. On the other side, the **World** manages the SimulationEngine, InfectionMonitor, CombatResolver, and Database."

---

## Slide 10 — Design Patterns

> "We implemented **6 design patterns**. **Template Method** in `Agent.run()` — the skeleton is fixed, subclasses fill in behavior. **Observer** through our `EventBus` — agents subscribe to events. **Singleton** for the Database — one connection, thread-safe. **Command** pattern for game actions. **Prototype** for zombie conversion — we clone the human's state. And **Strategy** in `movement.py` — behavior changes at runtime based on the President's orders."

---

## Slide 11 — Parallelism Model

> "Three types of threads. **Agent threads** — each of the 305 agents runs its own daemon thread with independent behavior loops. **Background daemons** — 5 engine threads for tick counting, win checking, infection spreading, strategy management, and database writing. And **locks** — grid lock, event lock, ID lock — to prevent race conditions. At the bottom, `threading.Event` objects coordinate global signals. Set once, all 310 threads react instantly."

---

## Slide 12 — Visualization

> "The visualization is a 3-step pipeline. **Snapshot** — copy the grid under a lock so agents aren't blocked. **Render** — move pre-allocated ovals on the Tkinter canvas. **Display** — everything stays on the main thread using `self.after()`. We pre-allocate the canvas pool so there's zero creation or deletion per frame, and it's GIL-safe — agents are never blocked by rendering."

---

## Slide 13 — Optimizations

> "Five key optimizations. **Batched DB writes** — 50 events per transaction. **Snapshot copy** instead of locking the full grid. **Manhattan distance** for pathfinding — no need for A* or Dijkstra. **Pre-allocated canvas** — zero memory allocations per frame. And the **land mask cached once** — 30,000 cells computed at startup and reused."

---

## Slide 14 — Challenges

> "Four major challenges. **Race conditions** when a Human transforms into a Zombie mid-tick — solved with an InfectionMonitor doing atomic swaps. **Circular imports** between Human and Zombie modules — solved using `__class__.__name__`. **UI thread safety** with Tkinter and 305 threads — solved with the snapshot copy and `self.after()`. And **SQLite's single-thread limitation** — solved with a dedicated writer thread and a queue."

---

## Slide 15 — Database

> "SQLite with two tables. **Simulations** stores all parameters and results — seed, strategy, probabilities, final counts. **Events** logs every action with a foreign key. We use **WAL mode** for concurrent reads, **batched inserts**, a **dedicated writer thread**, and in batch mode we run 100+ simulations automatically with statistical analysis."

---

## Slide 16 — Test results

> "**52 tests**, 100% success rate. **21 agent tests** for all roles and behaviors. **12 engine tests** for game mechanics. **17 database tests** for persistence and integrity. **2 snapshot tests** for the visualization pipeline. Plus batch analysis across 100+ runs comparing strategies with different random seeds."

---

## Slide 17 — Conclusion

> "To wrap up: our simulation produces **emergent behavior** from simple rules running in parallel. **310 threads with zero data corruption**. Every run is **unique** thanks to randomness and parallelism. **Strategy matters** — our batch data proves it. And we applied **6 real design patterns** to solve actual engineering problems."

---

## Slide 18 — Thank you

> "That's Guerra Mundial J. We're happy to take any questions."

---

*Tip: Keep each slide visible for ~30-45 seconds. Total presentation: ~9-10 minutes.*
