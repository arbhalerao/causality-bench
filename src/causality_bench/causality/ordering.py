from __future__ import annotations

from enum import Enum

from causality_bench.clocks import concurrent as vector_concurrent
from causality_bench.clocks import happens_before as vector_precedes
from causality_bench.simulation.event import Event


class Relation(str, Enum):
    BEFORE = "before"
    AFTER = "after"
    CONCURRENT = "concurrent"
    IDENTICAL = "identical"


def vector_relation(a: Event, b: Event) -> Relation:
    if a.event_id == b.event_id:
        return Relation.IDENTICAL
    if vector_precedes(a.vector_timestamp, b.vector_timestamp):
        return Relation.BEFORE
    if vector_precedes(b.vector_timestamp, a.vector_timestamp):
        return Relation.AFTER
    if vector_concurrent(a.vector_timestamp, b.vector_timestamp):
        return Relation.CONCURRENT

    # distinct events with equal vectors cannot occur in a correct execution
    raise AssertionError("distinct events carry identical vector timestamps")


def lamport_relation(a: Event, b: Event, tie_break: bool = False) -> Relation:
    """
    order two events using only the scalar timestamps

    a scalar cannot represent incomparability,
    so equal timestamps are reported as concurrent;
    tie_break models the common practice of extending Lamport time to a total order with the node identifier
    """
    if a.event_id == b.event_id:
        return Relation.IDENTICAL

    left = (a.lamport_timestamp, a.node_id) if tie_break else (a.lamport_timestamp,)
    right = (b.lamport_timestamp, b.node_id) if tie_break else (b.lamport_timestamp,)

    if left < right:
        return Relation.BEFORE
    if left > right:
        return Relation.AFTER
    return Relation.CONCURRENT
