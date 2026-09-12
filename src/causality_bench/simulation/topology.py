from __future__ import annotations

from enum import Enum

import networkx as nx

Neighbourhood = dict[int, tuple[int, ...]]


class Topology(str, Enum):
    RING = "ring"
    STAR = "star"
    COMPLETE = "complete"
    RANDOM = "random"
    SCALE_FREE = "scale_free"


DEFAULT_RANDOM_EDGE_PROBABILITY = 0.3
DEFAULT_ATTACHMENT_DEGREE = 2


def build_graph(topology: Topology | str, node_count: int, seed: int) -> nx.Graph:
    topology = Topology(topology)
    if node_count < 2:
        raise ValueError("a communication topology needs at least two nodes")

    if topology is Topology.RING:
        graph = nx.cycle_graph(node_count)
    elif topology is Topology.STAR:
        graph = nx.star_graph(node_count - 1)
    elif topology is Topology.COMPLETE:
        graph = nx.complete_graph(node_count)
    elif topology is Topology.RANDOM:
        graph = _connected_random_graph(node_count, seed)
    else:
        attachment = min(DEFAULT_ATTACHMENT_DEGREE, node_count - 1)
        graph = nx.barabasi_albert_graph(node_count, attachment, seed=seed)

    return graph


def build_neighbourhoods(topology: Topology | str, node_count: int, seed: int) -> Neighbourhood:
    graph = build_graph(topology, node_count, seed)
    return {node: tuple(sorted(graph.neighbors(node))) for node in range(node_count)}


def _connected_random_graph(node_count: int, seed: int) -> nx.Graph:
    """resample until connected so every node can participate in the execution"""
    for attempt in range(100):
        graph = nx.gnp_random_graph(
            node_count, DEFAULT_RANDOM_EDGE_PROBABILITY, seed=seed + attempt
        )
        if nx.is_connected(graph):
            return graph

    # fall back to a spanning ring so the experiment never silently degrades
    graph = nx.cycle_graph(node_count)
    return graph
