from __future__ import annotations

import itertools
from collections.abc import Iterator

from causality_bench.clocks import LamportClock, VectorClock
from causality_bench.simulation.event import Event, EventType
from causality_bench.simulation.message import ClockMetadata, Message


class Node:
    """
    a process that runs both clocks side by side over one execution

    running the clocks together keeps the comparison paired:
    both observe the identical sequence of events,
    so any difference in the recorded order comes from the representation rather than from a different execution
    """

    def __init__(
        self,
        node_id: int,
        node_count: int,
        event_ids: Iterator[int] | None = None,
    ) -> None:
        self.node_id = node_id
        self.node_count = node_count
        self.lamport = LamportClock(node_id=node_id)
        self.vector = VectorClock(node_id=node_id, node_count=node_count)
        self.events: list[Event] = []
        self._event_ids = event_ids if event_ids is not None else itertools.count()
        self._last_event_id: int | None = None

    def local_event(self, physical_time: float) -> Event:
        return self._record(EventType.LOCAL, physical_time, self.lamport.tick(), self.vector.tick())

    def prepare_send(self, physical_time: float) -> Event:
        return self._record(EventType.SEND, physical_time, self.lamport.send(), self.vector.send())

    def deliver(self, message: Message, physical_time: float) -> Event:
        lamport = self.lamport.receive(message.clock_metadata.lamport)
        vector = self.vector.receive(message.clock_metadata.vector)
        return self._record(
            EventType.RECEIVE,
            physical_time,
            lamport,
            vector,
            extra_dependency=message.send_event_id,
            message_id=message.message_id,
        )

    def clock_metadata(self, event: Event) -> ClockMetadata:
        return ClockMetadata(lamport=event.lamport_timestamp, vector=event.vector_timestamp)

    def _record(
        self,
        event_type: EventType,
        physical_time: float,
        lamport: int,
        vector: tuple[int, ...],
        extra_dependency: int | None = None,
        message_id: int | None = None,
    ) -> Event:
        dependencies: list[int] = []

        # program order gives the first dependency, delivery adds the second
        if self._last_event_id is not None:
            dependencies.append(self._last_event_id)
        if extra_dependency is not None:
            dependencies.append(extra_dependency)

        event = Event(
            event_id=next(self._event_ids),
            node_id=self.node_id,
            event_type=event_type,
            physical_time=physical_time,
            lamport_timestamp=lamport,
            vector_timestamp=vector,
            dependencies=tuple(dependencies),
            message_id=message_id,
        )
        self.events.append(event)
        self._last_event_id = event.event_id

        return event
