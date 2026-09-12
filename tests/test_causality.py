import itertools

import networkx as nx
import pytest

from causality_bench.causality import CausalGraph, Relation, lamport_relation, vector_relation
from causality_bench.experiments import all_scenarios
from causality_bench.experiments.scenarios import causal_chain_across_nodes, reordered_delivery
from causality_bench.simulation import EventType, SimulationConfig, run


@pytest.fixture
def relay():
    scenario = causal_chain_across_nodes()
    return scenario, CausalGraph(scenario.events)


def test_graph_edges_come_only_from_program_order_and_delivery(relay):
    scenario, graph = relay

    assert graph.graph.has_edge(scenario.id("origin"), scenario.id("send_ab"))
    assert graph.graph.has_edge(scenario.id("send_ab"), scenario.id("receive_b"))
    assert not graph.graph.has_edge(scenario.id("isolated"), scenario.id("receive_b"))


def test_graph_is_acyclic():
    result = run(SimulationConfig(nodes=6, events_per_node=80, seed=21))
    assert nx.is_directed_acyclic_graph(CausalGraph(result.events).graph)


def test_transitive_causality_across_three_nodes(relay):
    scenario, graph = relay

    assert graph.relation(scenario.id("origin"), scenario.id("terminal")) is Relation.BEFORE
    assert graph.relation(scenario.id("terminal"), scenario.id("origin")) is Relation.AFTER


def test_events_on_uncommunicating_nodes_are_concurrent(relay):
    scenario, graph = relay

    assert graph.relation(scenario.id("isolated"), scenario.id("send_ab")) is Relation.CONCURRENT


def test_an_event_is_identical_to_itself(relay):
    scenario, graph = relay
    event_id = scenario.id("origin")

    assert graph.relation(event_id, event_id) is Relation.IDENTICAL
    assert not graph.happens_before(event_id, event_id)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_reachability_index_agrees_with_graph_search(seed):
    result = run(SimulationConfig(nodes=4, events_per_node=35, seed=seed))
    graph = CausalGraph(result.events)
    ids = [e.event_id for e in result.events]

    for a, b in itertools.combinations(ids, 2):
        assert graph.relation(a, b) is graph.relation_by_search(a, b)


def test_transitive_pair_count_matches_the_transitive_closure():
    result = run(SimulationConfig(nodes=4, events_per_node=40, seed=8))
    graph = CausalGraph(result.events)

    assert graph.transitive_pairs() == nx.transitive_closure_dag(graph.graph).number_of_edges()


def test_dependencies_must_precede_their_event():
    result = run(SimulationConfig(nodes=4, events_per_node=20, seed=6))
    for event in result.events:
        assert all(dependency < event.event_id for dependency in event.dependencies)


def test_receive_events_carry_a_cross_node_dependency():
    result = run(SimulationConfig(nodes=5, events_per_node=60, seed=12))
    by_id = result.events_by_id

    receives = [e for e in result.events if e.event_type is EventType.RECEIVE]
    assert receives
    for event in receives:
        assert any(by_id[d].node_id != event.node_id for d in event.dependencies)


def test_lamport_reports_ties_as_indistinguishable(relay):
    scenario, _ = relay
    origin, isolated = scenario.event("origin"), scenario.event("isolated")

    assert origin.lamport_timestamp == isolated.lamport_timestamp
    assert lamport_relation(origin, isolated) is Relation.CONCURRENT
    assert lamport_relation(origin, isolated, tie_break=True) is Relation.BEFORE


def test_vector_relation_matches_the_ground_truth_graph():
    result = run(SimulationConfig(nodes=4, events_per_node=30, seed=15))
    graph = CausalGraph(result.events)

    for a, b in itertools.combinations(result.events, 2):
        assert vector_relation(a, b) is graph.relation(a.event_id, b.event_id)


@pytest.mark.parametrize("scenario", all_scenarios(), ids=lambda s: s.name)
def test_causality_implies_increasing_lamport_time(scenario):
    """the clock condition: a -> b implies L(a) < L(b)"""
    graph = CausalGraph(scenario.events)

    for a, b in itertools.combinations(scenario.events, 2):
        if graph.happens_before(a.event_id, b.event_id):
            assert a.lamport_timestamp < b.lamport_timestamp


@pytest.mark.parametrize("scenario", all_scenarios(), ids=lambda s: s.name)
def test_vector_order_characterises_causality(scenario):
    """the strong clock condition: V(a) < V(b) iff a -> b"""
    graph = CausalGraph(scenario.events)

    for a, b in itertools.combinations(scenario.events, 2):
        assert vector_relation(a, b) is graph.relation(a.event_id, b.event_id)


@pytest.mark.parametrize("scenario", all_scenarios(), ids=lambda s: s.name)
def test_vector_clocks_detect_every_concurrent_pair(scenario):
    graph = CausalGraph(scenario.events)

    for a, b in itertools.combinations(scenario.events, 2):
        truly_concurrent = graph.relation(a.event_id, b.event_id) is Relation.CONCURRENT
        assert (vector_relation(a, b) is Relation.CONCURRENT) == truly_concurrent


def test_smaller_lamport_time_does_not_imply_causality():
    """the central limitation: L(a) < L(b) carries no information about a -> b"""
    scenario = causal_chain_across_nodes()
    graph = CausalGraph(scenario.events)
    isolated, receive_b = scenario.event("isolated"), scenario.event("receive_b")

    assert isolated.lamport_timestamp < receive_b.lamport_timestamp
    assert graph.relation(isolated.event_id, receive_b.event_id) is Relation.CONCURRENT
    assert vector_relation(isolated, receive_b) is Relation.CONCURRENT


def test_lamport_falsely_orders_concurrent_events_in_a_random_execution():
    result = run(SimulationConfig(nodes=6, events_per_node=60, seed=19))
    graph = CausalGraph(result.events)

    falsely_ordered = [
        (a.event_id, b.event_id)
        for a, b in itertools.combinations(result.events, 2)
        if graph.relation(a.event_id, b.event_id) is Relation.CONCURRENT and lamport_relation(a, b) is not Relation.CONCURRENT
    ]
    assert falsely_ordered


def test_reordered_delivery_preserves_the_send_order_of_the_sender():
    scenario = reordered_delivery()
    graph = CausalGraph(scenario.events)

    assert graph.relation(scenario.id("send_first"), scenario.id("send_second")) is Relation.BEFORE
    assert graph.relation(scenario.id("send_first"), scenario.id("receive_second")) is Relation.BEFORE

    # the first message is delivered last, so its receive follows the other receive
    assert graph.relation(scenario.id("receive_second"), scenario.id("receive_first")) is Relation.BEFORE


def test_reordered_delivery_leaves_the_second_send_before_the_first_receive():
    scenario = reordered_delivery()

    first_receive = scenario.event("receive_first")
    second_send = scenario.event("send_second")
    assert second_send.lamport_timestamp < first_receive.lamport_timestamp
