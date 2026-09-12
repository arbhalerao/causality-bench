from __future__ import annotations

from collections.abc import Sequence

import networkx as nx
import numpy as np

from causality_bench.causality.ordering import Relation
from causality_bench.simulation.event import Event


class CausalGraph:
    """
    the happens-before relation of an execution, built without the clocks

    edges come only from program order within a node and from send -> receive,
    which is exactly Lamport's definition of ->;
    the clocks under evaluation are never consulted here
    """

    def __init__(self, events: Sequence[Event]) -> None:
        self.events = list(events)
        self.node_count = 1 + max((e.node_id for e in self.events), default=0)
        self._position = {event.event_id: i for i, event in enumerate(self.events)}
        self._by_id = {event.event_id: event for event in self.events}
        self.graph = self._build_graph()
        self._local_sequence = self._build_local_sequences()
        self._ancestor_index = self._build_ancestor_index()

    def __len__(self) -> int:
        return len(self.events)

    def event(self, event_id: int) -> Event:
        return self._by_id[event_id]

    def happens_before(self, a: int, b: int) -> bool:
        if a == b:
            return False

        # a -> b iff b's causal past already reaches a's position on a's node
        source = self._by_id[a]
        return bool(self._local_sequence[self._position[a]] <= self._ancestor_index[self._position[b], source.node_id])

    def relation(self, a: int, b: int) -> Relation:
        if a == b:
            return Relation.IDENTICAL
        if self.happens_before(a, b):
            return Relation.BEFORE
        if self.happens_before(b, a):
            return Relation.AFTER
        return Relation.CONCURRENT

    def reachable_by_search(self, a: int, b: int) -> bool:
        """authoritative but slow reachability used to validate the index"""
        return a != b and nx.has_path(self.graph, a, b)

    def relation_by_search(self, a: int, b: int) -> Relation:
        if a == b:
            return Relation.IDENTICAL
        if self.reachable_by_search(a, b):
            return Relation.BEFORE
        if self.reachable_by_search(b, a):
            return Relation.AFTER
        return Relation.CONCURRENT

    def transitive_pairs(self) -> int:
        """number of ordered pairs (a, b) with a -> b"""
        # a causal past is prefix-closed on every node, so the highest sequence
        # reached on a node is also the count of that node's events in the past
        counts = self._ancestor_index.sum(axis=1, dtype=np.int64)
        # each row counts the events in the causal past including the event itself
        return int(counts.sum() - len(self.events))

    def _build_graph(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        graph.add_nodes_from(event.event_id for event in self.events)
        graph.add_edges_from((dependency, event.event_id) for event in self.events for dependency in event.dependencies)
        return graph

    def _build_ancestor_index(self) -> np.ndarray:
        """
        per event, the highest local sequence number reached on every node

        event identifiers are allocated in occurrence order,
        so iterating over them is already a topological order of the DAG
        """
        index = np.zeros((len(self.events), self.node_count), dtype=np.int64)

        for i, event in enumerate(self.events):
            for dependency in event.dependencies:
                j = self._position[dependency]
                if j >= i:
                    raise ValueError("dependencies must precede their event in identifier order")
                np.maximum(index[i], index[j], out=index[i])

            index[i, event.node_id] = self._local_sequence[i]

        return index

    def _build_local_sequences(self) -> np.ndarray:
        sequences = np.zeros(len(self.events), dtype=np.int64)
        next_sequence = [0] * self.node_count

        for i, event in enumerate(self.events):
            next_sequence[event.node_id] += 1
            sequences[i] = next_sequence[event.node_id]

        return sequences
