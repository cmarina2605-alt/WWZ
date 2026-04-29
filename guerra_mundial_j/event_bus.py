"""
event_bus.py — Central event bus implementing the Observer design pattern.

Design Pattern: OBSERVER (publish / subscribe)
    Replaces the polling-based win condition checker with an event-driven
    system. Instead of a thread waking up every second to ask "has anyone
    died?", agents and the combat system ACT AS PUBLISHERS — they notify
    the EventBus the moment something relevant happens. SUBSCRIBERS (UI,
    stats panel, win logic) react instantly without polling.

Architecture:
    Publishers (agents, combat):
        event_bus.publish("zombie_killed", {"zombie_id": 42})
        event_bus.publish("human_infected", {"human_id": 7, "zombie_id": 3})
        event_bus.publish("antidote_complete", {"scientist_id": 12})

    Subscribers (engine win logic, UI, stats):
        event_bus.subscribe("zombie_killed", self._on_zombie_killed)
        event_bus.subscribe("human_infected", self._on_human_infected)
        event_bus.subscribe("antidote_complete", self._on_antidote)

Benefits over polling:
    - Zero-latency reaction: win conditions detected instantly.
    - No wasted CPU cycles: no thread spinning in a sleep loop.
    - Loose coupling: publishers don't know who listens.
    - Easy to extend: adding a new reaction is just .subscribe().

Thread safety:
    All operations are protected by a Lock. Callbacks execute on the
    publisher's thread — keep them fast or offload heavy work.

References:
    https://refactoring.guru/design-patterns/observer
"""

import threading
from typing import Callable, Dict, List, Any


# Type alias for subscriber callbacks
Callback = Callable[[Dict[str, Any]], None]


class EventBus:
    """
    Thread-safe publish/subscribe event bus.

    Any component can publish events (with a string topic and a data dict),
    and any component can subscribe to specific topics with a callback.

    Attributes:
        _subscribers (Dict[str, List[Callback]]): topic → list of callbacks.
        _lock (threading.Lock): protects the subscriber dict.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callback]] = {}
        self._lock: threading.Lock = threading.Lock()

    def subscribe(self, topic: str, callback: Callback) -> None:
        """
        Registers a callback for a specific event topic.

        Args:
            topic: Event name (e.g. "zombie_killed", "human_infected").
            callback: Function to call when the event fires.
                      Receives a single dict argument with event data.
        """
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)

    def publish(self, topic: str, data: Dict[str, Any] = None) -> None:
        """
        Publishes an event to all subscribers of a topic.

        Callbacks are executed synchronously on the publisher's thread.
        Keep them fast — heavy processing should be offloaded.

        Args:
            topic: Event name.
            data: Optional dict with event-specific data.
        """
        if data is None:
            data = {}

        with self._lock:
            listeners = list(self._subscribers.get(topic, []))

        for callback in listeners:
            try:
                callback(data)
            except Exception as exc:
                print(f"[EventBus] Error in subscriber for '{topic}': {exc}")

    def clear(self) -> None:
        """Removes all subscribers (used on simulation reset)."""
        with self._lock:
            self._subscribers.clear()

    def __repr__(self) -> str:
        with self._lock:
            topics = {k: len(v) for k, v in self._subscribers.items()}
        return f"EventBus(topics={topics})"
