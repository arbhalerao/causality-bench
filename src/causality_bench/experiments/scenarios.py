from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

from causality_bench.simulation.event import Event
from causality_bench.simulation.message import Message
from causality_bench.simulation.node import Node


@dataclass
class Scenario:
    """a hand-built execution with labelled events used for exact assertions"""

    name: str
    description: str
    node_count: int
    events: list[Event]
    labels: dict[str, int]

    def event(self, label: str) -> Event:
        by_id = {e.event_id: e for e in self.events}
        return by_id[self.labels[label]]

    def id(self, label: str) -> int:
        return self.labels[label]


@dataclass
class ExecutionBuilder:
    """
    builds a deterministic execution one step at a time

    physical time advances by one unit per step, which keeps deliveries after
    their sends while leaving the interleaving entirely under the caller
    """

    node_count: int
    _clock: itertools.count = field(default_factory=lambda: itertools.count(1))
    _messages: itertools.count = field(default_factory=itertools.count)
    labels: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        event_ids = itertools.count()
        self.nodes = [Node(node_id=i, node_count=self.node_count, event_ids=event_ids) for i in range(self.node_count)]

    def local(self, node_id: int, label: str) -> Event:
        return self._label(self.nodes[node_id].local_event(self._tick()), label)

    def send(self, sender: int, receiver: int, label: str) -> Message:
        node = self.nodes[sender]
        send_time = self._tick()
        event = self._label(node.prepare_send(send_time), label)
        return Message(
            message_id=next(self._messages),
            sender=sender,
            receiver=receiver,
            send_time=send_time,
            delivery_time=float("nan"),
            clock_metadata=node.clock_metadata(event),
            send_event_id=event.event_id,
        )

    def deliver(self, message: Message, label: str) -> Event:
        receiver = self.nodes[message.receiver]
        return self._label(receiver.deliver(message, self._tick()), label)

    def build(self, name: str, description: str) -> Scenario:
        events = sorted(
            (event for node in self.nodes for event in node.events),
            key=lambda e: e.event_id,
        )
        return Scenario(
            name=name,
            description=description,
            node_count=self.node_count,
            events=events,
            labels=dict(self.labels),
        )

    def _tick(self) -> float:
        return float(next(self._clock))

    def _label(self, event: Event, label: str) -> Event:
        if label in self.labels:
            raise ValueError(f"duplicate event label: {label}")
        self.labels[label] = event.event_id
        return event


def local_causal_chain() -> Scenario:
    builder = ExecutionBuilder(node_count=2)
    for step in range(3):
        builder.local(0, f"a{step}")
    return builder.build("local_causal_chain", "three events in program order on one node")


def message_causality() -> Scenario:
    builder = ExecutionBuilder(node_count=2)
    builder.local(0, "before_send")
    message = builder.send(0, 1, "send")
    builder.deliver(message, "receive")
    builder.local(1, "after_receive")
    return builder.build("message_causality", "a single message links two nodes")


def concurrent_events() -> Scenario:
    builder = ExecutionBuilder(node_count=2)
    builder.local(0, "a")
    builder.local(1, "b")
    return builder.build("concurrent_events", "two nodes act without communicating")


def multiple_concurrent_nodes() -> Scenario:
    builder = ExecutionBuilder(node_count=4)
    for node_id in range(4):
        builder.local(node_id, f"n{node_id}_first")
    for node_id in range(4):
        builder.local(node_id, f"n{node_id}_second")

    # node 0 and node 1 exchange a message, nodes 2 and 3 stay isolated
    message = builder.send(0, 1, "send")
    builder.deliver(message, "receive")
    builder.local(3, "late_isolated")
    return builder.build(
        "multiple_concurrent_nodes",
        "four nodes with one communicating pair and two isolated nodes",
    )


def reordered_delivery() -> Scenario:
    builder = ExecutionBuilder(node_count=2)
    first = builder.send(0, 1, "send_first")
    second = builder.send(0, 1, "send_second")

    # the network delivers the second message before the first
    builder.deliver(second, "receive_second")
    builder.deliver(first, "receive_first")
    return builder.build("reordered_delivery", "two messages delivered out of send order")


def causal_chain_across_nodes() -> Scenario:
    builder = ExecutionBuilder(node_count=3)
    builder.local(0, "origin")
    first = builder.send(0, 1, "send_ab")
    builder.local(2, "isolated")
    builder.deliver(first, "receive_b")
    second = builder.send(1, 2, "send_bc")
    builder.deliver(second, "receive_c")
    builder.local(2, "terminal")
    return builder.build("causal_chain_across_nodes", "causality propagates transitively through a relay")


SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "local_causal_chain": local_causal_chain,
    "message_causality": message_causality,
    "concurrent_events": concurrent_events,
    "multiple_concurrent_nodes": multiple_concurrent_nodes,
    "reordered_delivery": reordered_delivery,
    "causal_chain_across_nodes": causal_chain_across_nodes,
}


def all_scenarios() -> list[Scenario]:
    return [factory() for factory in SCENARIOS.values()]
