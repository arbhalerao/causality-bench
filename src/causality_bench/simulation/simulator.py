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
    failure_probability: float = 0.0
    mean_failure_duration: float = 0.0
    seed: int = 0

    def __post_init__(self) -> None:
        if self.nodes < 2:
            raise ValueError("simulation needs at least two nodes")
        if self.events_per_node < 1:
            raise ValueError("each node must take at least one step")
        if not 0.0 <= self.message_probability <= 1.0:
            raise ValueError("message probability must be a probability")
        if not 0.0 <= self.failure_probability < 1.0:
            raise ValueError("failure probability must be below one to guarantee progress")
        if self.failure_probability > 0.0 and self.mean_failure_duration <= 0.0:
            raise ValueError("a failing node needs a positive mean failure duration")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> SimulationConfig:
        known = set(cls.__dataclass_fields__)
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
    failures: int = 0
    total_downtime: float = 0.0
    messages_dropped_by_network: int = 0
    messages_dropped_by_failure: int = 0
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
    nodes = [Node(node_id=i, node_count=config.nodes, event_ids=event_ids) for i in range(config.nodes)]

    messages: list[Message] = []
    delivered: set[int] = set()
    remaining_steps = [config.events_per_node] * config.nodes

    # a crashed node keeps its clock state across the outage;
    # a node that lost its logical time on recovery could no longer satisfy the clock condition
    recovers_at = [0.0] * config.nodes
    failures = 0
    downtime = 0.0
    dropped_by_network = 0
    dropped_by_failure = 0

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
            if now < recovers_at[message.receiver]:
                dropped_by_failure += 1
                continue
            nodes[message.receiver].deliver(message, now)
            delivered.add(message.message_id)
            continue

        node_id = payload
        if config.failure_probability > 0.0 and streams[node_id]["failure"].random() < (config.failure_probability):
            outage = float(streams[node_id]["failure"].exponential(config.mean_failure_duration))
            recovers_at[node_id] = now + outage
            failures += 1
            downtime += outage

            # the pending step is resumed on recovery,
            # so the workload per node stays fixed and only the execution structure changes
            heapq.heappush(queue, (recovers_at[node_id], next(order), _Kind.STEP, node_id))
            continue

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
            if network.drops(streams[node_id]["loss"]):
                dropped_by_network += 1
            else:
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
        failures=failures,
        total_downtime=downtime,
        messages_dropped_by_network=dropped_by_network,
        messages_dropped_by_failure=dropped_by_failure,
    )
