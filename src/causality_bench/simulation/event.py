from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from causality_bench.clocks import Vector


class EventType(str, Enum):
    LOCAL = "local"
    SEND = "send"
    RECEIVE = "receive"


@dataclass(frozen=True, slots=True)
class Event:
    """
    a single point in a distributed execution

    dependencies hold the immediate causal predecessors of the event
    and are derived only from program order and message delivery,
    never from the clocks
    """

    event_id: int
    node_id: int
    event_type: EventType
    physical_time: float
    lamport_timestamp: int
    vector_timestamp: Vector
    dependencies: tuple[int, ...] = ()
    message_id: int | None = None
