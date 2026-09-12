import itertools
from math import comb

import pytest

from causality_bench.causality import CausalGraph, Relation, lamport_relation
from causality_bench.experiments import benchmark_clock_operations, evaluate
from causality_bench.experiments.metrics import causal_metrics, metadata_metrics
from causality_bench.experiments.scenarios import concurrent_events, local_causal_chain
from causality_bench.simulation import SimulationConfig, run


def metrics_for(scenario):
    return causal_metrics(scenario.events, CausalGraph(scenario.events))


def test_a_purely_local_chain_has_no_concurrency():
    metrics = metrics_for(local_causal_chain())

    assert metrics.total_pairs == 3
    assert metrics.ordered_pairs == 3
    assert metrics.concurrent_pairs == 0
    assert metrics.causal_density == 1.0


def test_two_isolated_events_are_concurrent_and_tied_under_lamport():
    metrics = metrics_for(concurrent_events())

    assert metrics.concurrent_pairs == 1
    assert metrics.lamport_tied_pairs == 1
    assert metrics.lamport_false_orderings == 0
    assert metrics.lamport_concurrency_recall == 1.0


def test_pair_counts_partition_the_event_pairs():
    result = run(SimulationConfig(nodes=6, events_per_node=80, seed=31))
    metrics = causal_metrics(result.events, CausalGraph(result.events))

    assert metrics.total_pairs == comb(metrics.events, 2)
    assert metrics.ordered_pairs + metrics.concurrent_pairs == metrics.total_pairs
    assert metrics.lamport_tied_pairs + metrics.lamport_false_orderings == metrics.concurrent_pairs


@pytest.mark.parametrize("seed", [2, 4])
def test_closed_form_counts_match_exhaustive_enumeration(seed):
    result = run(SimulationConfig(nodes=4, events_per_node=30, seed=seed))
    graph = CausalGraph(result.events)
    metrics = causal_metrics(result.events, graph)

    ordered = concurrent = tied = false_ordered = 0
    for a, b in itertools.combinations(result.events, 2):
        truth = graph.relation(a.event_id, b.event_id)
        if truth is Relation.CONCURRENT:
            concurrent += 1
            if lamport_relation(a, b) is Relation.CONCURRENT:
                tied += 1
            else:
                false_ordered += 1
        else:
            ordered += 1

    assert (ordered, concurrent) == (metrics.ordered_pairs, metrics.concurrent_pairs)
    assert (tied, false_ordered) == (metrics.lamport_tied_pairs, metrics.lamport_false_orderings)


def test_equal_lamport_timestamps_never_occur_on_causally_ordered_events():
    result = run(SimulationConfig(nodes=5, events_per_node=40, seed=23))
    graph = CausalGraph(result.events)

    for a, b in itertools.combinations(result.events, 2):
        if a.lamport_timestamp == b.lamport_timestamp:
            assert graph.relation(a.event_id, b.event_id) is Relation.CONCURRENT


def test_vector_clocks_lose_no_causal_information():
    result = run(SimulationConfig(nodes=6, events_per_node=60, seed=29))
    metrics = causal_metrics(result.events, CausalGraph(result.events))

    assert metrics.vector_false_ordering_rate == 0.0
    assert metrics.vector_concurrency_recall == 1.0
    assert metrics.vector_order_precision == 1.0


@pytest.mark.parametrize("nodes", [2, 8, 32])
def test_vector_metadata_grows_linearly_in_the_node_count(nodes):
    result = run(SimulationConfig(nodes=nodes, events_per_node=40, seed=1))
    metrics = metadata_metrics(result)

    assert metrics.lamport_timestamp_bytes == 8
    assert metrics.vector_timestamp_bytes == 8 * nodes
    assert metrics.metadata_amplification == nodes
    assert metrics.measured_vector_retained_bytes > metrics.measured_lamport_retained_bytes


def test_message_metadata_is_charged_once_per_message():
    result = run(SimulationConfig(nodes=8, events_per_node=100, seed=3))
    metrics = metadata_metrics(result)

    assert metrics.messages == len(result.messages)
    assert metrics.vector_message_metadata_bytes == 64 * len(result.messages)


def test_clock_benchmark_reports_positive_times_for_every_operation():
    timings = benchmark_clock_operations(nodes=8, repetitions=200)

    assert set(timings) == {
        "lamport_tick_ns",
        "lamport_send_ns",
        "lamport_receive_ns",
        "vector_tick_ns",
        "vector_send_ns",
        "vector_receive_ns",
    }
    assert all(value > 0 for value in timings.values())


def test_evaluate_produces_a_flat_record_of_scalars():
    result = run(SimulationConfig(nodes=4, events_per_node=40, seed=5))
    record = evaluate(result, repetitions=100)

    assert record["nodes"] == 4
    assert record["seed"] == 5
    assert all(isinstance(value, (int, float, str)) for value in record.values())
