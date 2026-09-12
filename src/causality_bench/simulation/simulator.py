from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from causality_bench.simulation.event import Event
from causality_bench.simulation.message import Message
from causality_bench.simulation.network import DelayDistribution, Network
from causality_bench.simulation.node import Node
from causality_bench.simulation.topology import Topology


@dataclass(frozen=True)
class SimulationConfig:
    nodes: int
    events_per_node: int
    message_probability: float = 0.25
    topology: str = Topology.COMPLETE.value
    delay_distribution: str = DelayDistribution.EXPONENTIAL.value
    mean_delay: float = 10.0
    mean_interarrival: float = 1.0
    loss_probability: float = 0.0
    seed: int = 0

    def __post_init__(self) -> None:
        if self.nodes < 2:
            raise ValueError("simulation needs at least two nodes")
        if self.events_per_node < 1:
            raise ValueError("each node must take at least one step")
        if not 0.0 <= self.message_probability <= 1.0:
            raise ValueError("message probability must be a probability")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> SimulationConfig:
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"unknown configuration keys: {sorted(unknown)}")
        return cls(**values)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SimulationResult:
    config: SimulationConfig
    events: list[Event]
    messages: list[Message]
    delivered_message_ids: set[int]
    wall_clock_seconds: float
    final_time: float
    events_by_id: dict[int, Event] = field(init=False)

    def __post_init__(self) -> None:
        self.events_by_id = {event.event_id: event for event in self.events}

    @property
    def lost_messages(self) -> int:
        return len(self.messages) - len(self.delivered_message_ids)


class _Kind(int, Enum):
    STEP = 0
    DELIVERY = 1


# stream roles are fixed so that adding a feature that consumes randomness does not perturb the draws of the experiments already recorded
_STREAMS = ("workload", "delay", "loss", "failure")


def _node_streams(seed: int, nodes: int) -> list[dict[str, np.random.Generator]]:
    root = np.random.SeedSequence(seed)
    return [
        dict(
            zip(
                _STREAMS,
                (np.random.default_rng(s) for s in child.spawn(len(_STREAMS))),
                strict=True,
            )
        )
        for child in root.spawn(nodes)
    ]


def run(config: SimulationConfig) -> SimulationResult:
    """execute one deterministic run; identical config and seed give identical output"""
    streams = _node_streams(config.seed, config.nodes)
    network = Network.build(
        node_count=config.nodes,
        topology=config.topology,
        delay_distribution=config.delay_distribution,
        mean_delay=config.mean_delay,
        seed=config.seed,
        loss_probability=config.loss_probability,
    )

    event_ids = itertools.count()
    message_ids = itertools.count()
    nodes = [
        Node(node_id=i, node_count=config.nodes, event_ids=event_ids) for i in range(config.nodes)
    ]

    messages: list[Message] = []
    delivered: set[int] = set()
    remaining_steps = [config.events_per_node] * config.nodes

    # a strictly increasing sequence number makes the queue a total order even when two entries share a timestamp
    order = itertools.count()
    queue: list[tuple[float, int, _Kind, Any]] = []
    for node_id in range(config.nodes):
        first_step = float(streams[node_id]["workload"].exponential(config.mean_interarrival))
        heapq.heappush(queue, (first_step, next(order), _Kind.STEP, node_id))

    started = time.perf_counter()
    now = 0.0
    while queue:
        now, _, kind, payload = heapq.heappop(queue)

        if kind is _Kind.DELIVERY:
            message: Message = payload
            nodes[message.receiver].deliver(message, now)
            continue

        node_id = payload
        node = nodes[node_id]
        workload = streams[node_id]["workload"]
        neighbours = network.neighbours(node_id)

        if neighbours and workload.random() < config.message_probability:
            receiver = int(neighbours[workload.integers(len(neighbours))])
            send_event = node.prepare_send(now)
            delay = network.sample_delay(streams[node_id]["delay"])
            message = Message(
                message_id=next(message_ids),
                sender=node_id,
                receiver=receiver,
                send_time=now,
                delivery_time=now + delay,
                clock_metadata=node.clock_metadata(send_event),
                send_event_id=send_event.event_id,
            )
            messages.append(message)
            if not network.drops(streams[node_id]["loss"]):
                delivered.add(message.message_id)
                heapq.heappush(queue, (message.delivery_time, next(order), _Kind.DELIVERY, message))
        else:
            node.local_event(now)

        remaining_steps[node_id] -= 1
        if remaining_steps[node_id] > 0:
            next_step = now + float(workload.exponential(config.mean_interarrival))
            heapq.heappush(queue, (next_step, next(order), _Kind.STEP, node_id))

    elapsed = time.perf_counter() - started
    events = sorted((event for node in nodes for event in node.events), key=lambda e: e.event_id)
    return SimulationResult(
        config=config,
        events=events,
        messages=messages,
        delivered_message_ids=delivered,
        wall_clock_seconds=elapsed,
        final_time=now,
    )
