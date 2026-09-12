from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from causality_bench.experiments.statistics import summarize
from causality_bench.visualization.style import (
    FIGURE_DIR,
    LAMPORT,
    MUTED_INK,
    ORDINAL_BLUE,
    SECONDARY_INK,
    SERIES,
    VECTOR,
    save_figure,
)

NODE_TICKS = [2, 4, 8, 16, 32, 64, 128]
DELAY_LAWS = ("deterministic", "uniform", "exponential")


def _line_with_interval(ax, summary, x: str, metric: str, colour: str, label: str) -> None:
    ax.plot(summary[x], summary[f"{metric}_mean"], color=colour, marker="o", label=label)
    ax.fill_between(
        summary[x],
        summary[f"{metric}_ci_low"],
        summary[f"{metric}_ci_high"],
        color=colour,
        alpha=0.18,
        linewidth=0,
    )


def _interval_arms(summary, metric: str):
    return [
        summary[f"{metric}_mean"] - summary[f"{metric}_ci_low"],
        summary[f"{metric}_ci_high"] - summary[f"{metric}_mean"],
    ]


def _label_endpoint(ax, summary, x: str, metric: str, colour: str, label: str) -> None:
    ax.annotate(
        label,
        xy=(summary[x].iloc[-1], summary[f"{metric}_mean"].iloc[-1]),
        xytext=(6, 0),
        textcoords="offset points",
        va="center",
        fontsize=7.5,
        color=colour,
    )


def _asymptotic_slope(summary, x: str, metric: str, points: int = 4) -> float:
    """log-log slope over the largest configurations, where fixed costs matter least"""
    xs = np.log2(summary[x].to_numpy(dtype=float)[-points:])
    ys = np.log2(summary[f"{metric}_mean"].to_numpy(dtype=float)[-points:])
    return float(np.polyfit(xs, ys, 1)[0])


def _annotate_slope(ax, summary, x: str, metric: str, colour: str) -> None:
    slope = _asymptotic_slope(summary, x, metric)
    ax.annotate(
        f"slope {slope:.2f}",
        xy=(summary[x].iloc[-1], summary[f"{metric}_mean"].iloc[-1]),
        xytext=(-4, 10),
        textcoords="offset points",
        ha="right",
        fontsize=7.5,
        color=colour,
    )


def _node_axis(ax) -> None:
    ax.set_xscale("log", base=2)
    ax.set_xticks(NODE_TICKS)
    ax.set_xticklabels([str(n) for n in NODE_TICKS])
    ax.set_xlabel("nodes in the system")


def timestamp_size_vs_nodes(scaling: pd.DataFrame, directory: Path = FIGURE_DIR) -> Path:
    summary = summarize(
        scaling,
        ["nodes"],
        [
            "lamport_timestamp_bytes",
            "vector_timestamp_bytes",
            "vector_message_metadata_bytes",
            "lamport_message_metadata_bytes",
        ],
    )

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.0, 3.4))
    _line_with_interval(left, summary, "nodes", "lamport_timestamp_bytes", LAMPORT, "Lamport")
    _line_with_interval(left, summary, "nodes", "vector_timestamp_bytes", VECTOR, "Vector")
    _node_axis(left)
    left.set_yscale("log", base=2)
    left.set_ylabel("bytes per timestamp")
    left.set_title("timestamp width", fontsize=9)
    left.legend(loc="upper left")

    _line_with_interval(right, summary, "nodes", "lamport_message_metadata_bytes", LAMPORT, "Lamport")
    _line_with_interval(right, summary, "nodes", "vector_message_metadata_bytes", VECTOR, "Vector")
    _node_axis(right)
    right.set_yscale("log", base=10)
    right.set_ylabel("total clock bytes on the wire")
    right.set_title("metadata carried by all messages in a run", fontsize=9)
    right.legend(loc="upper left")

    fig.tight_layout()
    return save_figure(
        fig,
        "timestamp_size_vs_nodes",
        "Figure 5. timestamp width and total message metadata against system size, 30 seeds per "
        "point. a Lamport timestamp is one 64-bit counter at every size; a dense vector timestamp "
        "is one counter per node, so the per-message cost grows linearly in the node count.",
        directory,
    )


def runtime_vs_nodes(scaling: pd.DataFrame, directory: Path = FIGURE_DIR) -> Path:
    summary = summarize(
        scaling,
        ["nodes"],
        ["lamport_receive_ns", "vector_receive_ns", "simulation_seconds"],
    )

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.0, 3.4))
    _line_with_interval(left, summary, "nodes", "lamport_receive_ns", LAMPORT, "Lamport")
    _line_with_interval(left, summary, "nodes", "vector_receive_ns", VECTOR, "Vector")
    _annotate_slope(left, summary, "nodes", "vector_receive_ns", VECTOR)
    _annotate_slope(left, summary, "nodes", "lamport_receive_ns", LAMPORT)
    _node_axis(left)
    left.set_yscale("log", base=2)
    left.set_ylabel("time per receive (ns)")
    left.set_title("cost of one receive-side clock update", fontsize=9)
    left.legend(loc="upper left")

    _line_with_interval(right, summary, "nodes", "simulation_seconds", SERIES[0], "simulation")
    _annotate_slope(right, summary, "nodes", "simulation_seconds", SERIES[0])
    _node_axis(right)
    right.set_yscale("log", base=2)
    right.set_ylabel("wall clock (s)")
    right.set_title("time to execute one run", fontsize=9)

    fig.tight_layout()
    return save_figure(
        fig,
        "runtime_vs_nodes",
        "Figure 6. measured clock cost against system size on log-log axes, 30 seeds per point "
        "with 95% confidence intervals; the annotated slopes are fitted over the largest four "
        "sizes. the Lamport receive is a constant-time maximum and stays flat. the vector receive "
        "is O(N) in theory but measures below slope 1, because the fixed per-call cost of the "
        "implementation still contributes at these sizes.",
        directory,
    )


def memory_vs_nodes(scaling: pd.DataFrame, directory: Path = FIGURE_DIR) -> Path:
    frame = scaling.copy()
    frame["lamport_bytes_per_event"] = frame.measured_lamport_retained_bytes / frame.events
    frame["vector_bytes_per_event"] = frame.measured_vector_retained_bytes / frame.events
    summary = summarize(frame, ["nodes"], ["lamport_bytes_per_event", "vector_bytes_per_event"])

    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    _line_with_interval(ax, summary, "nodes", "lamport_bytes_per_event", LAMPORT, "Lamport")
    _line_with_interval(ax, summary, "nodes", "vector_bytes_per_event", VECTOR, "Vector")
    ax.plot(
        summary["nodes"],
        8 * summary["nodes"],
        color=MUTED_INK,
        linewidth=1.0,
        label="analytic model (8N bytes)",
    )
    _node_axis(ax)
    ax.set_yscale("log", base=2)
    ax.set_ylabel("retained bytes per stored event")
    ax.set_title("memory held by one timestamp per event")
    ax.legend(loc="upper left")

    return save_figure(
        fig,
        "memory_vs_nodes",
        "Figure 7. allocation measured with tracemalloc while retaining one timestamp per event, "
        "against the analytic 8N-byte model. the measured curve sits above the model by the fixed "
        "per-object overhead of the Python container and is a lower bound, because small integers "
        "are interned and shared between timestamps.",
        directory,
    )


def false_ordering_vs_nodes(scaling: pd.DataFrame, directory: Path = FIGURE_DIR) -> Path:
    summary = summarize(scaling, ["nodes"], ["lamport_false_ordering_rate", "concurrency_ratio"])

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.0, 3.4))
    _line_with_interval(left, summary, "nodes", "lamport_false_ordering_rate", LAMPORT, "Lamport")
    left.axhline(0.0, color=VECTOR, linewidth=1.6)
    left.annotate(
        "Vector: 0 by construction",
        xy=(NODE_TICKS[0], 0.0),
        xytext=(0, 7),
        textcoords="offset points",
        fontsize=7.5,
        color=VECTOR,
    )
    _node_axis(left)
    left.set_ylim(-0.05, 1.05)
    left.set_ylabel("share of concurrent pairs given an order")
    left.set_title("false ordering imposed on concurrent events", fontsize=9)

    _line_with_interval(right, summary, "nodes", "concurrency_ratio", SERIES[0], "concurrent")
    _node_axis(right)
    right.set_ylabel("share of all event pairs")
    right.set_title("concurrency present in the execution", fontsize=9)

    fig.tight_layout()
    return save_figure(
        fig,
        "false_ordering_vs_nodes",
        "Figure 8. left: of the event pairs that are genuinely concurrent, the fraction that "
        "Lamport timestamps separate anyway; the remainder are timestamp ties. right: how much "
        "concurrency the execution contains at all. more nodes means more concurrency and a "
        "larger share of it misrepresented. 30 seeds per point, 95% confidence intervals.",
        directory,
    )


def concurrency_vs_message_rate(message_rate: pd.DataFrame, directory: Path = FIGURE_DIR) -> Path:
    summary = summarize(
        message_rate,
        ["message_probability"],
        ["concurrency_ratio", "causal_density", "lamport_false_ordering_rate"],
    )

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.0, 3.4))
    _line_with_interval(left, summary, "message_probability", "concurrency_ratio", SERIES[0], "concurrent")
    left.set_ylabel("share of all event pairs")
    left.set_title("concurrency against communication intensity", fontsize=9)

    _line_with_interval(right, summary, "message_probability", "lamport_false_ordering_rate", LAMPORT, "Lamport")
    right.set_ylabel("share of concurrent pairs given an order")
    right.set_title("false ordering against communication intensity", fontsize=9)

    for ax in (left, right):
        ax.set_xlabel("probability that a step sends a message")

    fig.tight_layout()
    return save_figure(
        fig,
        "concurrency_vs_message_rate",
        "Figure 9. communication removes concurrency: as more steps send messages, a larger share "
        "of event pairs becomes causally ordered and less of the execution is left for a scalar "
        "clock to misorder. eight nodes, 30 seeds per point, 95% confidence intervals.",
        directory,
    )


def topology_comparison(topology: pd.DataFrame, directory: Path = FIGURE_DIR) -> Path:
    summary = summarize(topology, ["topology"], ["concurrency_ratio", "lamport_false_ordering_rate"]).sort_values("concurrency_ratio_mean")

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.0, 3.4))
    errors = _interval_arms(summary, "concurrency_ratio")
    left.barh(
        summary["topology"],
        summary["concurrency_ratio_mean"],
        xerr=errors,
        color=SERIES[0],
        height=0.5,
        error_kw={"ecolor": SECONDARY_INK, "elinewidth": 1.0, "capsize": 3},
    )
    left.set_title("concurrency in the execution", fontsize=9)
    left.set_xlabel("share of all event pairs")

    # a truncated axis rules out bars, so the second panel uses point estimates
    right.errorbar(
        summary["lamport_false_ordering_rate_mean"],
        summary["topology"],
        xerr=_interval_arms(summary, "lamport_false_ordering_rate"),
        fmt="o",
        color=SERIES[0],
        ecolor=SECONDARY_INK,
        elinewidth=1.0,
        capsize=3,
        markersize=6,
    )
    right.set_title("false ordering under Lamport time", fontsize=9)
    right.set_xlabel("share of concurrent pairs given an order")
    right.set_xlim(0.985, 1.0)

    for ax in (left, right):
        ax.grid(axis="y", visible=False)

    fig.tight_layout()
    return save_figure(
        fig,
        "topology_comparison",
        "Figure 10. thirty-two nodes at a fixed message rate, varying only which pairs may "
        "communicate. sparse structures leave far more of the execution concurrent, and the "
        "concurrency they leave is almost entirely misordered by a scalar clock. the right panel "
        "is drawn as point estimates because its axis is truncated. 30 seeds per topology, 95% "
        "confidence intervals.",
        directory,
    )


def failure_results(failure: pd.DataFrame, directory: Path = FIGURE_DIR) -> Path:
    summary = summarize(
        failure,
        ["loss_probability", "failure_probability"],
        ["concurrency_ratio", "messages_lost", "events"],
    )

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.0, 3.4))
    for colour, (loss, group) in zip(ORDINAL_BLUE, summary.groupby("loss_probability"), strict=True):
        label = f"loss {loss:.2f}"
        _line_with_interval(left, group, "failure_probability", "concurrency_ratio", colour, label)
        _line_with_interval(right, group, "failure_probability", "messages_lost", colour, label)

    left.set_ylabel("share of all event pairs concurrent")
    left.set_title("concurrency under loss and crash-recovery", fontsize=9)
    right.set_ylabel("messages never delivered")
    right.set_title("undelivered messages", fontsize=9)

    for ax in (left, right):
        ax.set_xlabel("per-step probability that a node crashes")
        ax.legend(loc="upper left", title="network loss", title_fontsize=7.5)

    fig.tight_layout()
    return save_figure(
        fig,
        "failure_results",
        "Figure 11. message loss and temporary node failure both remove message deliveries, which "
        "removes causal edges and leaves more of the execution concurrent. the clocks continue to "
        "order what they observe; neither recovers the information carried by a lost message. "
        "eight nodes, 30 seeds per point, 95% confidence intervals.",
        directory,
    )


def concurrency_vs_delay(delay: pd.DataFrame, directory: Path = FIGURE_DIR) -> Path:
    summary = summarize(delay, ["delay_distribution", "mean_delay"], ["concurrency_ratio"])

    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    for colour, law in zip(SERIES[: len(DELAY_LAWS)], DELAY_LAWS, strict=True):
        group = summary[summary.delay_distribution == law]
        _line_with_interval(ax, group, "mean_delay", "concurrency_ratio", colour, law)
        _label_endpoint(ax, group, "mean_delay", "concurrency_ratio", colour, law)

    ax.set_xscale("log", base=10)
    ax.set_xticks([1.0, 10.0, 50.0])
    ax.set_xticklabels(["1", "10", "50"])
    ax.set_xlabel("mean message delay (in units of the mean inter-event time)")
    ax.set_ylabel("share of all event pairs concurrent")
    ax.set_title("concurrency against delay magnitude and delay law")
    ax.set_xlim(right=95)
    ax.legend(loc="upper left")

    return save_figure(
        fig,
        "concurrency_vs_delay",
        "Figure 12. delay magnitude dominates: messages in flight for longer leave more of the "
        "execution unordered. at a fixed mean, the delay law is a second-order effect that only "
        "separates once the mean is large, where a heavier-tailed law delivers many messages early "
        "and recovers causal edges. eight nodes, 30 seeds per point, 95% confidence intervals.",
        directory,
    )
