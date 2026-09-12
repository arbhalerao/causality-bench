"""render every figure in the report from the recorded raw results"""

import pandas as pd

from causality_bench.provenance import read_csv
from causality_bench.simulation import SimulationConfig, run
from causality_bench.visualization import (
    apply_style,
    causal_dag,
    concurrency_vs_delay,
    concurrency_vs_message_rate,
    execution_timeline,
    failure_results,
    false_ordering_vs_nodes,
    lamport_timeline,
    memory_vs_nodes,
    runtime_vs_nodes,
    timestamp_size_vs_nodes,
    topology_comparison,
    vector_timeline,
)

# small enough to read every timestamp in the space-time figures
ILLUSTRATION = SimulationConfig(
    nodes=3,
    events_per_node=6,
    message_probability=0.4,
    mean_delay=1.5,
    mean_interarrival=2.5,
    seed=11,
)


def raw(name: str) -> pd.DataFrame:
    return read_csv(f"results/raw/{name}.csv")


def main() -> None:
    apply_style()
    illustration = run(ILLUSTRATION)

    figures = [
        execution_timeline(illustration),
        lamport_timeline(illustration),
        vector_timeline(illustration),
        causal_dag(illustration),
        timestamp_size_vs_nodes(raw("scaling")),
        runtime_vs_nodes(raw("scaling")),
        memory_vs_nodes(raw("scaling")),
        false_ordering_vs_nodes(raw("scaling")),
        concurrency_vs_message_rate(raw("message_rate")),
        topology_comparison(raw("topology")),
        failure_results(raw("failure")),
        concurrency_vs_delay(raw("delay")),
    ]

    for path in figures:
        print(path)


if __name__ == "__main__":
    main()
