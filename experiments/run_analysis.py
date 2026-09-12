"""aggregate every raw result into the processed tables cited by the report"""

from pathlib import Path

import pandas as pd

from causality_bench.experiments.statistics import (
    log_log_slope,
    paired_comparison,
    summarize,
    write_processed,
)
from causality_bench.provenance import read_csv

RAW_DIR = Path("results/raw")

CAUSAL_METRICS = [
    "events",
    "causal_density",
    "concurrency_ratio",
    "lamport_false_ordering_rate",
    "lamport_concurrency_recall",
    "lamport_order_precision",
    "mean_vector_nonzero_entries",
]
COST_METRICS = [
    "lamport_timestamp_bytes",
    "vector_timestamp_bytes",
    "lamport_message_metadata_bytes",
    "vector_message_metadata_bytes",
    "measured_lamport_retained_bytes",
    "measured_vector_retained_bytes",
    "lamport_receive_ns",
    "vector_receive_ns",
    "lamport_tick_ns",
    "vector_tick_ns",
    "simulation_seconds",
]

GROUPINGS = {
    "baseline": ["nodes"],
    "scaling": ["nodes"],
    "message_rate": ["message_probability"],
    "delay": ["delay_distribution", "mean_delay"],
    "topology": ["topology"],
    "failure": ["loss_probability", "failure_probability"],
}

# empirical exponents are reported against the analytic complexity of each cost
SCALING_FITS = [
    "vector_receive_ns",
    "lamport_receive_ns",
    "vector_tick_ns",
    "lamport_tick_ns",
    "vector_timestamp_bytes",
    "measured_vector_retained_bytes",
    "measured_lamport_retained_bytes",
    "simulation_seconds",
    "events",
]


def raw(name: str) -> pd.DataFrame:
    return read_csv(RAW_DIR / f"{name}.csv")


def main() -> None:
    written = []

    for name, group_by in GROUPINGS.items():
        frame = raw(name)
        summary = summarize(frame, group_by, CAUSAL_METRICS + COST_METRICS)
        written.append(write_processed(summary, f"{name}_summary"))

    scaling = raw("scaling")
    written.append(
        write_processed(
            pd.DataFrame([log_log_slope(scaling, "nodes", m) for m in SCALING_FITS]),
            "scaling_exponents",
        )
    )
    written.append(
        write_processed(
            paired_comparison(scaling, ["nodes"], "lamport_receive_ns", "vector_receive_ns"),
            "receive_cost_paired",
        )
    )
    written.append(
        write_processed(
            paired_comparison(
                scaling,
                ["nodes"],
                "measured_lamport_retained_bytes",
                "measured_vector_retained_bytes",
            ),
            "retained_memory_paired",
        )
    )

    for path in written:
        print(path)


if __name__ == "__main__":
    main()
