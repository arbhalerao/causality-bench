from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from causality_bench.causality.dag import CausalGraph
from causality_bench.causality.ordering import Relation
from causality_bench.simulation.event import EventType
from causality_bench.simulation.simulator import SimulationResult
from causality_bench.visualization.style import (
    FIGURE_DIR,
    MUTED_INK,
    SECONDARY_INK,
    SERIES,
    SURFACE,
    save_figure,
)

EVENT_STYLE = {
    EventType.LOCAL: ("local", SERIES[0], "o"),
    EventType.SEND: ("send", SERIES[1], ">"),
    EventType.RECEIVE: ("receive", SERIES[2], "s"),
}


def _draw_space_time(ax, result: SimulationResult) -> None:
    nodes = result.config.nodes
    for node_id in range(nodes):
        ax.axhline(node_id, color=MUTED_INK, linewidth=0.7, zorder=1)

    for event_type, (label, colour, marker) in EVENT_STYLE.items():
        selected = [e for e in result.events if e.event_type is event_type]
        ax.scatter(
            [e.physical_time for e in selected],
            [e.node_id for e in selected],
            color=colour,
            marker=marker,
            s=42,
            label=label,
            zorder=3,
            edgecolors=SURFACE,
            linewidths=1.0,
        )

    by_id = result.events_by_id
    for event in result.events:
        if event.event_type is not EventType.RECEIVE:
            continue
        send = next(by_id[d] for d in event.dependencies if by_id[d].node_id != event.node_id)
        ax.annotate(
            "",
            xy=(event.physical_time, event.node_id),
            xytext=(send.physical_time, send.node_id),
            arrowprops={
                "arrowstyle": "->",
                "color": MUTED_INK,
                "linewidth": 0.9,
                "shrinkA": 5,
                "shrinkB": 5,
            },
            zorder=2,
        )

    ax.set_yticks(range(nodes))
    ax.set_yticklabels([f"node {i}" for i in range(nodes)])
    ax.set_ylim(nodes - 0.5, -0.5)
    ax.set_xlabel("simulated time (delay units)")
    ax.grid(axis="y", visible=False)


def execution_timeline(result: SimulationResult, directory: Path = FIGURE_DIR) -> Path:
    fig, ax = plt.subplots(figsize=(9.0, 3.0))
    _draw_space_time(ax, result)
    ax.set_title("distributed execution as a space-time diagram", pad=24)
    ax.legend(loc="lower left", ncol=3, bbox_to_anchor=(0.0, 1.02))

    return save_figure(
        fig,
        "execution_timeline",
        "Figure 1. one deterministic execution. horizontal lines are nodes, markers are events, "
        "and arrows are messages. the arrows are the only edges that cross nodes, and together "
        "with program order they define the ground-truth happens-before relation.",
        directory,
    )


def _annotate_timestamps(ax, result, formatter) -> None:
    # alternate the label side per node so consecutive timestamps do not collide
    seen = [0] * result.config.nodes

    for event in result.events:
        above = seen[event.node_id] % 2 == 0
        seen[event.node_id] += 1
        ax.annotate(
            formatter(event),
            xy=(event.physical_time, event.node_id),
            xytext=(0, 9 if above else -15),
            textcoords="offset points",
            ha="center",
            fontsize=6.5,
            color=SECONDARY_INK,
        )


def _highlight_concurrent_pair(ax, result, graph: CausalGraph):
    """find a pair that Lamport orders but that is genuinely concurrent"""
    for a in result.events:
        for b in result.events:
            if a.lamport_timestamp < b.lamport_timestamp and (graph.relation(a.event_id, b.event_id) is Relation.CONCURRENT):
                for event in (a, b):
                    ax.scatter(
                        [event.physical_time],
                        [event.node_id],
                        s=190,
                        facecolors="none",
                        edgecolors=SERIES[4],
                        linewidths=1.6,
                        zorder=4,
                    )
                return a, b
    return None


def lamport_timeline(result: SimulationResult, directory: Path = FIGURE_DIR) -> Path:
    graph = CausalGraph(result.events)
    fig, ax = plt.subplots(figsize=(9.0, 3.2))
    _draw_space_time(ax, result)
    _annotate_timestamps(ax, result, lambda e: str(e.lamport_timestamp))
    pair = _highlight_concurrent_pair(ax, result, graph)
    ax.set_title("Lamport timestamps over the same execution", pad=24)
    ax.legend(loc="lower left", ncol=3, bbox_to_anchor=(0.0, 1.02))

    detail = ""
    if pair:
        a, b = pair
        detail = (
            f" the circled pair has L={a.lamport_timestamp} and L={b.lamport_timestamp}, "
            "so the scalar order claims a precedence that the execution does not contain."
        )

    return save_figure(
        fig,
        "lamport_timestamps",
        "Figure 2. scalar Lamport time printed above each event. every message arrow increases the "
        "timestamp, so causality is preserved, but the converse fails." + detail,
        directory,
    )


def vector_timeline(result: SimulationResult, directory: Path = FIGURE_DIR) -> Path:
    fig, ax = plt.subplots(figsize=(9.0, 3.2))
    _draw_space_time(ax, result)
    _annotate_timestamps(ax, result, lambda e: ",".join(str(v) for v in e.vector_timestamp))
    ax.set_title("Vector timestamps over the same execution", pad=24)
    ax.legend(loc="lower left", ncol=3, bbox_to_anchor=(0.0, 1.02))

    return save_figure(
        fig,
        "vector_timestamps",
        "Figure 3. the same events carrying one counter per node. two timestamps are ordered only "
        "when one dominates the other entrywise, so incomparable events stay incomparable and no "
        "false precedence is introduced.",
        directory,
    )


def causal_dag(result: SimulationResult, directory: Path = FIGURE_DIR) -> Path:
    graph = CausalGraph(result.events)
    depth = _causal_depth(graph.graph)
    positions = {event.event_id: (depth[event.event_id], event.node_id) for event in result.events}

    by_id = result.events_by_id
    program_edges = [(u, v) for u, v in graph.graph.edges if by_id[u].node_id == by_id[v].node_id]
    message_edges = [(u, v) for u, v in graph.graph.edges if by_id[u].node_id != by_id[v].node_id]

    fig, ax = plt.subplots(figsize=(9.0, 3.2))
    for edges, colour, label in (
        (program_edges, MUTED_INK, "program order"),
        (message_edges, SERIES[1], "message"),
    ):
        nx.draw_networkx_edges(
            graph.graph,
            positions,
            edgelist=edges,
            ax=ax,
            edge_color=colour,
            width=1.0,
            arrowsize=8,
            node_size=90,
        )
        ax.plot([], [], color=colour, label=label)

    nx.draw_networkx_nodes(
        graph.graph,
        positions,
        ax=ax,
        node_size=90,
        node_color=SERIES[0],
        edgecolors=SURFACE,
        linewidths=1.0,
    )

    # the NetworkX drawing helpers disable the axis decorations
    ax.tick_params(left=True, labelleft=True, bottom=True, labelbottom=True)
    ax.set_yticks(range(result.config.nodes))
    ax.set_yticklabels([f"node {i}" for i in range(result.config.nodes)])
    ax.set_ylim(result.config.nodes - 0.5, -0.5)
    ax.set_xlabel("causal depth (longest chain of predecessors)")
    ax.set_title("ground-truth causal DAG", pad=24)
    ax.legend(loc="lower left", ncol=2, bbox_to_anchor=(0.0, 1.02))
    ax.grid(axis="y", visible=False)

    return save_figure(
        fig,
        "causal_dag",
        "Figure 4. the reference against which both clocks are scored, laid out by causal depth. "
        "it is derived only from program order and message delivery; no timestamp is consulted.",
        directory,
    )


def _causal_depth(graph: nx.DiGraph) -> dict[int, int]:
    depth: dict[int, int] = {}
    for node in nx.topological_sort(graph):
        predecessors = list(graph.predecessors(node))
        depth[node] = 1 + max((depth[p] for p in predecessors), default=-1)
    return depth
