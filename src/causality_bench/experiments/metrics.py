from __future__ import annotations

import time
import tracemalloc
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from math import comb
from typing import Any

import numpy as np

from causality_bench.causality.dag import CausalGraph
from causality_bench.clocks import LamportClock, VectorClock
from causality_bench.simulation.event import Event, EventType
from causality_bench.simulation.simulator import SimulationResult

# a sparse vector entry pays for a 32-bit node index next to its 64-bit counter
SPARSE_ENTRY_BYTES = 12


@dataclass(frozen=True)
class CausalMetrics:
    """
    exact pair statistics over the execution

    every quantity is counted in closed form rather than sampled:
    the number of causally ordered pairs comes from the reachability index,
    and every pair of events sharing a Lamport timestamp is necessarily concurrent because
    the clock condition forbids equal timestamps on ordered events
    """

    events: int
    total_pairs: int
    ordered_pairs: int
    concurrent_pairs: int
    causal_density: float
    concurrency_ratio: float
    lamport_tied_pairs: int
    lamport_false_orderings: int
    lamport_false_ordering_rate: float
    lamport_concurrency_recall: float
    lamport_order_precision: float
    lamport_causal_recall: float
    vector_false_ordering_rate: float
    vector_concurrency_recall: float
    vector_order_precision: float
    vector_causal_recall: float


@dataclass(frozen=True)
class MetadataMetrics:
    nodes: int
    events: int
    messages: int
    lamport_timestamp_bytes: int
    vector_timestamp_bytes: int
    lamport_event_metadata_bytes: int
    vector_event_metadata_bytes: int
    lamport_message_metadata_bytes: int
    vector_message_metadata_bytes: int
    metadata_amplification: float
    mean_vector_nonzero_entries: float
    sparse_vector_timestamp_bytes: float
    measured_lamport_retained_bytes: int
    measured_vector_retained_bytes: int


@dataclass(frozen=True)
class RuntimeMetrics:
    """
    measured cost per clock operation, separate from the analytic complexity

    Lamport operations are O(1) and vector operations are O(N) in the number of nodes;
    the timings below are what those cost in this implementation
    """

    nodes: int
    simulation_seconds: float
    graph_build_seconds: float
    lamport_tick_ns: float
    lamport_send_ns: float
    lamport_receive_ns: float
    vector_tick_ns: float
    vector_send_ns: float
    vector_receive_ns: float


def causal_metrics(events: Sequence[Event], graph: CausalGraph) -> CausalMetrics:
    event_count = len(graph)
    total_pairs = comb(event_count, 2)
    ordered_pairs = graph.transitive_pairs()
    concurrent_pairs = total_pairs - ordered_pairs

    counts = Counter(event.lamport_timestamp for event in events)
    tied_pairs = sum(comb(n, 2) for n in counts.values())
    false_orderings = concurrent_pairs - tied_pairs

    return CausalMetrics(
        events=event_count,
        total_pairs=total_pairs,
        ordered_pairs=ordered_pairs,
        concurrent_pairs=concurrent_pairs,
        causal_density=_ratio(ordered_pairs, total_pairs),
        concurrency_ratio=_ratio(concurrent_pairs, total_pairs),
        lamport_tied_pairs=tied_pairs,
        lamport_false_orderings=false_orderings,
        lamport_false_ordering_rate=_ratio(false_orderings, concurrent_pairs),
        lamport_concurrency_recall=_ratio(tied_pairs, concurrent_pairs),
        lamport_order_precision=_ratio(ordered_pairs, ordered_pairs + false_orderings),
        lamport_causal_recall=1.0,
        vector_false_ordering_rate=0.0,
        vector_concurrency_recall=1.0,
        vector_order_precision=1.0,
        vector_causal_recall=1.0,
    )


def metadata_metrics(result: SimulationResult) -> MetadataMetrics:
    nodes = result.config.nodes
    events = result.events
    lamport_bytes = LamportClock.timestamp_bytes(nodes)
    vector_bytes = VectorClock.timestamp_bytes(nodes)
    nonzero = float(np.mean([sum(1 for x in e.vector_timestamp if x) for e in events]))
    retained = _measure_retained_bytes(events)

    return MetadataMetrics(
        nodes=nodes,
        events=len(events),
        messages=len(result.messages),
        lamport_timestamp_bytes=lamport_bytes,
        vector_timestamp_bytes=vector_bytes,
        lamport_event_metadata_bytes=lamport_bytes * len(events),
        vector_event_metadata_bytes=vector_bytes * len(events),
        lamport_message_metadata_bytes=lamport_bytes * len(result.messages),
        vector_message_metadata_bytes=vector_bytes * len(result.messages),
        metadata_amplification=vector_bytes / lamport_bytes,
        mean_vector_nonzero_entries=nonzero,
        sparse_vector_timestamp_bytes=nonzero * SPARSE_ENTRY_BYTES,
        measured_lamport_retained_bytes=retained[0],
        measured_vector_retained_bytes=retained[1],
    )


def runtime_metrics(
    result: SimulationResult,
    graph_build_seconds: float,
    repetitions: int = 20000,
) -> RuntimeMetrics:
    nodes = result.config.nodes
    return RuntimeMetrics(
        nodes=nodes,
        simulation_seconds=result.wall_clock_seconds,
        graph_build_seconds=graph_build_seconds,
        **benchmark_clock_operations(nodes, repetitions),
    )


def benchmark_clock_operations(nodes: int, repetitions: int = 20000) -> dict[str, float]:
    """time one clock operation in isolation, away from the simulation loop"""
    lamport = LamportClock(node_id=0)
    vector = VectorClock(node_id=0, node_count=nodes)
    remote = tuple(range(nodes))

    return {
        "lamport_tick_ns": _time_ns(lamport.tick, repetitions),
        "lamport_send_ns": _time_ns(lamport.send, repetitions),
        "lamport_receive_ns": _time_ns(lambda: lamport.receive(1), repetitions),
        "vector_tick_ns": _time_ns(vector.tick, repetitions),
        "vector_send_ns": _time_ns(vector.send, repetitions),
        "vector_receive_ns": _time_ns(lambda: vector.receive(remote), repetitions),
    }


def event_type_counts(result: SimulationResult) -> dict[str, int]:
    counts = Counter(event.event_type.value for event in result.events)
    return {f"{name.value}_events": counts.get(name.value, 0) for name in EventType}


def evaluate(result: SimulationResult, repetitions: int = 20000) -> dict[str, Any]:
    """full metric record for one simulation run"""
    started = time.perf_counter()
    graph = CausalGraph(result.events)
    graph_seconds = time.perf_counter() - started

    record: dict[str, Any] = dict(result.config.as_dict())
    record.update(asdict(causal_metrics(result.events, graph)))
    record.update(asdict(metadata_metrics(result)))
    record.update(asdict(runtime_metrics(result, graph_seconds, repetitions)))
    record.update(event_type_counts(result))
    record["messages_lost"] = result.lost_messages
    record["final_logical_time"] = result.final_time
    return record


def _ratio(numerator: int, denominator: int) -> float:
    return float(numerator) / denominator if denominator else 0.0


def _time_ns(operation, repetitions: int) -> float:
    started = time.perf_counter_ns()
    for _ in range(repetitions):
        operation()
    return (time.perf_counter_ns() - started) / repetitions


def _measure_retained_bytes(events: Sequence[Event]) -> tuple[int, int]:
    """
    allocation cost of holding one timestamp per event in Python objects

    small integers are interned,
    so this measurement is a lower bound on the real footprint and is reported next to the analytic byte model rather than in place of it
    """
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    scalars = [int(e.lamport_timestamp) for e in events]
    lamport_bytes = tracemalloc.get_traced_memory()[0] - before

    # tuple() on a tuple returns the same object, so copy through a list to
    # force a fresh allocation per timestamp
    before = tracemalloc.get_traced_memory()[0]
    vectors = [tuple(list(e.vector_timestamp)) for e in events]
    vector_bytes = tracemalloc.get_traced_memory()[0] - before
    tracemalloc.stop()

    # keep both alive until the measurement is taken
    del scalars, vectors
    return lamport_bytes, vector_bytes
