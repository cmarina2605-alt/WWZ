"""
human.py — Clases de agentes humanos de la simulación.

Implementa la jerarquía de humanos que pueblan el grid:

    Human (Agent)   — base: tiene miedo (fear) y empatía (empathy).
    ├── Normal       — ciudadano sin habilidades especiales; huye de zombis.
    ├── Scientist    — navega activamente hacia el laboratorio (LAB_POS) para
    │                  trabajar en el antídoto; huye si detecta zombis cerca.
    ├── Military     — si fuerza > FORCE_FLEE_THRESHOLD, persigue zombis en
    │                  lugar de huir; usa munición para aumentar prob. de matar.
    └── Politician   — emite alertas nacionales (national_alert) al ver zombis,
                       lo que acelera la respuesta de los militares.

Mecánicas clave:
    - Miedo (fear): aumenta al ver zombis, disminuye con el tiempo.
      Un miedo alto activa el estado "running" y puede penalizar atributos.
    - Pánico social (panic_spread): si ≥4 vecinos están corriendo, el agente
      entra en pánico aunque no vea zombis directamente.
    - Infección: Human.infect() marca el estado como "infected"; la conversión
      real a Zombie la gestiona el InfectionMonitor del Engine.
    - Antídoto: cuando un Scientist acumula suficientes ticks en el lab,
      activa antidote_ready y empuja un evento al EventLog.
"""

import random
import threading
from typing import Tuple, Optional, TYPE_CHECKING

import config
from agents.base_agent import Agent, antidote_ready, national_alert

if TYPE_CHECKING:
    from simulation.world import World


class Human(Agent):
    """
    Agente humano base.

    Extiende Agent añadiendo empatía y miedo, que modulan las
    decisiones de huida, agrupamiento y combate.

    Attributes:
        empathy (int): Tendencia a ayudar a otros (0-100).
        fear (int): Nivel de pánico actual (0-100); aumenta al ver zombis.
        role (str): Rol del humano (normal/scientist/military/politician).
    """

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        force: int = 50,
        age: int = 30,
        empathy: int = 50,
        fear: int = 10,
    ) -> None:
        """
        Inicializa un humano con empatía y miedo.

        Args:
            pos: Posición inicial (x, y).
            world: Referencia al mundo compartido.
            force: Fuerza física (0-100).
            age: Edad del agente.
            empathy: Nivel de empatía (0-100).
            fear: Miedo inicial (0-100).
        """
        super().__init__(pos=pos, world=world, force=force, age=age)
        self.empathy: int = max(0, min(100, empathy))
        self.fear: int = max(0, min(100, fear))
        self.role: str = "normal"

    # ------------------------------------------------------------------
    # Lógica principal
    # ------------------------------------------------------------------

    def update(self) -> None:
        """
        Lógica de actualización por tick para humanos.

        1. Detecta zombis cercanos y actualiza el miedo.
        2. Calcula la siguiente posición (via movement).
        3. Comprueba encuentros con zombis en la nueva posición.
        4. Actualiza el estado según el contexto.
        """
        from simulation import movement, combat

        if not self.is_alive():
            return

        # Detectar zombis en rango de visión
        nearby = self.world.get_agents_in_radius(self.pos, config.VISION_HUMAN)
        zombies_nearby = [a for a in nearby if a.__class__.__name__ == "Zombie"]

        # Actualizar miedo
        self._update_fear(len(zombies_nearby))

        # Calcular próxima posición
        next_pos = movement.calculate_next_pos(self, self.world)

        # Comprobar si hay zombi en la celda destino o adyacente
        agents_at_dest = self.world.get_agents_in_radius(next_pos, 1)
        zombies_at_dest = [a for a in agents_at_dest if a.__class__.__name__ == "Zombie"]

        if zombies_at_dest:
            zombie = zombies_at_dest[0]
            combat.resolve_encounter(self, zombie, self.world)
        else:
            # Mover al agente
            self.world.move_agent(self, next_pos)

        # Propagación del pánico
        movement.panic_spread(self, self.world)

    def _update_fear(self, zombie_count: int) -> None:
        """
        Actualiza el nivel de miedo según la cantidad de zombis visibles.

        Args:
            zombie_count: Número de zombis detectados en el rango de visión.
        """
        if zombie_count > 0:
            self.fear = min(100, self.fear + zombie_count * 10)
            self.set_state("running")
        else:
            self.fear = max(0, self.fear - 5)
            if self.fear < 20 and self.state == "running":
                self.set_state("calm")

    def get_color(self) -> str:
        """Retorna el color según el rol del humano."""
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_NORMAL

    def infect(self) -> None:
        """
        Marca al humano como infectado.

        Esto inicia el proceso de conversión a zombi, gestionado
        por el motor de simulación.
        """
        self.set_state("infected")

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.agent_id}, role={self.role}, "
            f"pos={self.pos}, fear={self.fear}, state={self.state})"
        )


# ---------------------------------------------------------------------------
# Subclases especializadas
# ---------------------------------------------------------------------------

class Normal(Human):
    """
    Humano corriente sin habilidades especiales.

    Comportamiento estándar: huye de los zombis y busca refugio.
    """

    def __init__(self, pos: Tuple[int, int], world: "World", **kwargs) -> None:
        super().__init__(pos=pos, world=world, **kwargs)
        self.role = "normal"

    def get_color(self) -> str:
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_NORMAL


class Scientist(Human):
    """
    Científico que puede contribuir al antídoto.

    Attributes:
        intelligence (int): Nivel de inteligencia (0-100); reduce tiempo
            necesario para completar el antídoto.
        antidote_progress (int): Ticks acumulados trabajando en el antídoto.
        in_lab (bool): Si está actualmente en la base científica.
    """

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        intelligence: int = 70,
        **kwargs,
    ) -> None:
        """
        Inicializa un Scientist con inteligencia adicional.

        Args:
            intelligence: Nivel de inteligencia (0-100).
        """
        super().__init__(pos=pos, world=world, **kwargs)
        self.role = "scientist"
        self.intelligence: int = max(0, min(100, intelligence))
        self.antidote_progress: int = 0
        self.in_lab: bool = False

    def update(self) -> None:
        """
        Actualización del científico.

        Prioridad:
        1. Si hay zombis cerca → huir (comportamiento humano estándar).
        2. Si está en el lab → trabajar en el antídoto.
        3. Si no está en el lab → moverse hacia él.
        """
        from simulation import movement

        if not self.is_alive():
            return

        # Detectar si estamos cerca del laboratorio
        dist_to_lab = self.distance_to(config.LAB_POS)
        if dist_to_lab <= config.LAB_RADIUS:
            self.in_lab = True

        # Si hay zombis cerca, huir tiene prioridad sobre el laboratorio
        nearby = self.world.get_agents_in_radius(self.pos, config.VISION_HUMAN)
        zombies_nearby = [a for a in nearby if a.__class__.__name__ == "Zombie"]

        if zombies_nearby:
            self.in_lab = False  # Salir del lab si hay peligro
            super().update()
        elif self.in_lab and not antidote_ready.is_set():
            self._work_on_antidote()
            self._update_fear(0)  # El científico se calma trabajando
        elif not self.in_lab:
            # Moverse hacia el laboratorio
            self._update_fear(0)
            next_pos = movement.move_towards(self.pos, config.LAB_POS, self.world)
            self.world.move_agent(self, next_pos)
        else:
            super().update()

    def _work_on_antidote(self) -> None:
        """
        Avanza en la investigación del antídoto.

        El progreso aumenta según la inteligencia del científico.
        Cuando se completa, activa el evento global antidote_ready.
        """
        progress_rate = 1 + int(self.intelligence / 20)
        self.antidote_progress += progress_rate

        ticks_needed = config.ANTIDOTE_TICKS - int(self.intelligence * 2)
        if self.antidote_progress >= ticks_needed:
            antidote_ready.set()
            national_alert.set()
            self.world.push_event(
                "antidote",
                f"💉 ¡ANTÍDOTO COMPLETADO! El científico #{self.agent_id} ha encontrado la cura",
            )

    def get_color(self) -> str:
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_SCIENTIST


class Military(Human):
    """
    Militar con fuerza aumentada y comportamiento de combate agresivo.

    A diferencia de los civiles, no huye si su fuerza supera
    FORCE_FLEE_THRESHOLD; en su lugar, entra en estado "fighting".

    Attributes:
        ammo (int): Munición disponible (afecta probabilidad de matar zombi).
    """

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        ammo: int = 10,
        **kwargs,
    ) -> None:
        """
        Inicializa un Military con bonus de fuerza y munición.

        Args:
            ammo: Munición inicial.
        """
        # Aplicar bonus de fuerza
        force = kwargs.pop("force", 50)
        force = min(100, force + config.FORCE_MILITARY_BONUS)
        super().__init__(pos=pos, world=world, force=force, **kwargs)
        self.role = "military"
        self.ammo: int = ammo

    def update(self) -> None:
        """
        Actualización del militar.

        Si la fuerza supera el umbral, busca activamente zombis para
        combatir en lugar de huir.

        Con estrategia "military_first": radio de visión ampliado (VISION_ZOMBIE)
        y umbral de fuerza reducido a 30, para que casi todos los militares luchen.
        """
        from simulation import movement, combat

        if not self.is_alive():
            return

        strategy = getattr(self.world, "strategy", "none")
        if strategy == "military_first":
            vision = config.VISION_ZOMBIE
            force_threshold = 30
        else:
            vision = config.VISION_HUMAN
            force_threshold = config.FORCE_FLEE_THRESHOLD

        nearby = self.world.get_agents_in_radius(self.pos, vision)
        zombies_nearby = [a for a in nearby if a.__class__.__name__ == "Zombie"]

        if zombies_nearby and self.force > force_threshold:
            # Comportamiento agresivo: acercarse al zombi más cercano
            self.set_state("fighting")
            closest = min(zombies_nearby, key=lambda z: self.distance_to(z.pos))
            # Mover hacia el zombi
            next_pos = movement.move_towards(self.pos, closest.pos, self.world)
            agents_at = self.world.get_agents_in_radius(next_pos, 0)
            if any(a.__class__.__name__ == "Zombie" for a in agents_at):
                combat.resolve_encounter(self, closest, self.world)
            else:
                self.world.move_agent(self, next_pos)
        else:
            # Comportamiento estándar (huida)
            super().update()

    def use_ammo(self) -> bool:
        """
        Consume una unidad de munición.

        Returns:
            bool: True si había munición disponible y se consumió.
        """
        if self.ammo > 0:
            self.ammo -= 1
            return True
        return False

    def get_color(self) -> str:
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_MILITARY


class Politician(Human):
    """
    Político con alta empatía que puede emitir alertas nacionales.

    Tiene la capacidad de activar el evento national_alert cuando
    detecta una situación crítica, lo que acelera la respuesta militar.

    Attributes:
        influence (int): Nivel de influencia (0-100); afecta la probabilidad
            de que la alerta sea efectiva.
        alert_cooldown (int): Ticks restantes hasta poder emitir otra alerta.
    """

    ALERT_COOLDOWN_TICKS: int = 50

    def __init__(
        self,
        pos: Tuple[int, int],
        world: "World",
        influence: int = 80,
        **kwargs,
    ) -> None:
        """
        Inicializa un Politician con alta empatía e influencia.

        Args:
            influence: Nivel de influencia política (0-100).
        """
        empathy = kwargs.pop("empathy", 80)
        super().__init__(pos=pos, world=world, empathy=empathy, **kwargs)
        self.role = "politician"
        self.influence: int = max(0, min(100, influence))
        self.alert_cooldown: int = 0
        self._alert_messages: list[str] = [
            "📨 Mensaje llega a Casa Blanca",
            "📨 Declarado estado de emergencia nacional",
            "📨 Protocolo Z activado",
        ]

    def update(self) -> None:
        """
        Actualización del político.

        Intenta emitir alertas nacionales al detectar zombis y
        sigue comportamiento humano estándar.
        """
        if not self.is_alive():
            return

        if self.alert_cooldown > 0:
            self.alert_cooldown -= 1

        nearby = self.world.get_agents_in_radius(self.pos, config.VISION_HUMAN)
        zombies_nearby = [a for a in nearby if a.__class__.__name__ == "Zombie"]

        if zombies_nearby and self.alert_cooldown == 0:
            self._emit_alert()

        super().update()

    def _emit_alert(self) -> None:
        """
        Emite una alerta nacional si las condiciones se cumplen.

        La probabilidad de éxito depende del nivel de influencia.
        """
        if random.random() < self.influence / 100.0:
            national_alert.set()
            self.alert_cooldown = self.ALERT_COOLDOWN_TICKS
            msg = random.choice(self._alert_messages)
            self.world.push_event("alert", msg)

    def get_color(self) -> str:
        if self.state == "infected":
            return config.COLOR_INFECTED
        if self.state == "dead":
            return config.COLOR_DEAD
        return config.COLOR_POLITICIAN
