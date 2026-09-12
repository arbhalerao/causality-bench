import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")

from causality_bench.experiments.runner import ExperimentSpec, run_experiment  # noqa: E402
from causality_bench.simulation import SimulationConfig, run  # noqa: E402
from causality_bench.visualization import (  # noqa: E402
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


@pytest.fixture(scope="module", autouse=True)
def style():
    apply_style()


@pytest.fixture(scope="module")
def execution():
    return run(SimulationConfig(nodes=3, events_per_node=5, message_probability=0.4, seed=2))


def sweep(name, base, sweep_values):
    spec = ExperimentSpec(
        name=name,
        base={"events_per_node": 20, "message_probability": 0.3, **base},
        seeds=(1, 2),
        sweep=sweep_values,
        benchmark_repetitions=20,
    )
    return run_experiment(spec, progress=False)


@pytest.fixture(scope="module")
def scaling():
    return sweep("scaling", {}, {"nodes": [2, 4]})


@pytest.mark.parametrize("figure", [execution_timeline, lamport_timeline, vector_timeline, causal_dag])
def test_execution_figures_are_written(figure, execution, tmp_path):
    path = figure(execution, tmp_path)
    assert path.exists() and path.stat().st_size > 0


@pytest.mark.parametrize(
    "figure",
    [timestamp_size_vs_nodes, runtime_vs_nodes, memory_vs_nodes, false_ordering_vs_nodes],
)
def test_scaling_figures_are_written(figure, scaling, tmp_path):
    path = figure(scaling, tmp_path)
    assert path.exists() and path.stat().st_size > 0


def test_message_rate_figure_is_written(tmp_path):
    frame = sweep("rate", {"nodes": 3}, {"message_probability": [0.1, 0.5]})
    assert concurrency_vs_message_rate(frame, tmp_path).exists()


def test_topology_figure_is_written(tmp_path):
    frame = sweep("topology", {"nodes": 4}, {"topology": ["ring", "complete"]})
    assert topology_comparison(frame, tmp_path).exists()


def test_delay_figure_is_written(tmp_path):
    frame = sweep(
        "delay",
        {"nodes": 3},
        {
            "delay_distribution": ["deterministic", "uniform", "exponential"],
            "mean_delay": [1.0, 10.0],
        },
    )
    assert concurrency_vs_delay(frame, tmp_path).exists()


def test_failure_figure_is_written(tmp_path):
    frame = sweep(
        "failure",
        {"nodes": 4, "mean_failure_duration": 10.0},
        {"loss_probability": [0.0, 0.05, 0.1, 0.25], "failure_probability": [0.0, 0.01]},
    )
    assert failure_results(frame, tmp_path).exists()


def test_figures_are_not_written_until_requested(tmp_path):
    assert not list(tmp_path.iterdir())


def test_summary_columns_are_present_for_plotting(scaling):
    assert isinstance(scaling, pd.DataFrame)
    assert {"nodes", "vector_receive_ns", "concurrency_ratio"} <= set(scaling.columns)
