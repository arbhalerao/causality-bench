import itertools

import pytest

from causality_bench.simulation import (
    EventType,
    Message,
    Node,
    SimulationConfig,
    build_neighbourhoods,
    run,
)


def make_nodes(count):
    ids = itertools.count()
    return [Node(node_id=i, node_count=count, event_ids=ids) for i in range(count)]


def deliver(sender, receiver, send_event, message_id, delivery_time):
    message = Message(
        message_id=message_id,
        sender=sender.node_id,
        receiver=receiver.node_id,
        send_time=send_event.physical_time,
        delivery_time=delivery_time,
        clock_metadata=sender.clock_metadata(send_event),
        send_event_id=send_event.event_id,
    )
    return receiver.deliver(message, delivery_time)


def test_local_events_stamp_both_clocks():
    node = Node(node_id=0, node_count=2)
    first = node.local_event(physical_time=1.0)

    assert first.event_type is EventType.LOCAL
    assert first.lamport_timestamp == 1
    assert first.vector_timestamp == (1, 0)


def test_program_order_is_the_only_dependency_of_a_local_event():
    node = Node(node_id=0, node_count=1)
    first = node.local_event(0.0)
    second = node.local_event(1.0)

    assert first.dependencies == ()
    assert second.dependencies == (first.event_id,)


def test_receive_depends_on_program_order_and_the_send():
    sender, receiver = make_nodes(2)
    prior = receiver.local_event(0.0)
    send_event = sender.prepare_send(1.0)
    receive_event = deliver(sender, receiver, send_event, message_id=0, delivery_time=5.0)

    assert receive_event.event_type is EventType.RECEIVE
    assert set(receive_event.dependencies) == {prior.event_id, send_event.event_id}
    assert receive_event.message_id == 0


def test_first_event_on_a_node_that_only_receives_depends_on_the_send_alone():
    sender, receiver = make_nodes(2)
    send_event = sender.prepare_send(1.0)
    receive_event = deliver(sender, receiver, send_event, message_id=0, delivery_time=2.0)

    assert receive_event.dependencies == (send_event.event_id,)


def test_delivery_merges_both_clock_representations():
    sender, receiver = make_nodes(2)
    for _ in range(3):
        receiver.local_event(0.0)

    send_event = sender.prepare_send(1.0)
    receive_event = deliver(sender, receiver, send_event, message_id=0, delivery_time=2.0)

    assert receive_event.lamport_timestamp == 4
    assert receive_event.vector_timestamp == (1, 4)


def test_event_ids_are_unique_across_nodes():
    nodes = make_nodes(3)
    for node in nodes:
        for _ in range(4):
            node.local_event(0.0)

    ids = [event.event_id for node in nodes for event in node.events]
    assert len(set(ids)) == len(ids)


def stamps(result):
    return [(e.node_id, e.lamport_timestamp, e.vector_timestamp) for e in result.events]


def test_identical_config_and_seed_reproduce_the_run():
    config = SimulationConfig(nodes=6, events_per_node=120, seed=7)
    assert stamps(run(config)) == stamps(run(config))


def test_different_seeds_produce_different_executions():
    left = run(SimulationConfig(nodes=6, events_per_node=120, seed=1))
    right = run(SimulationConfig(nodes=6, events_per_node=120, seed=2))
    assert stamps(left) != stamps(right)


def test_every_node_takes_the_configured_number_of_steps():
    config = SimulationConfig(nodes=5, events_per_node=40, seed=3)
    result = run(config)

    steps = [sum(1 for e in result.events if e.node_id == n and e.event_type is not EventType.RECEIVE) for n in range(config.nodes)]
    assert steps == [config.events_per_node] * config.nodes


def test_all_sent_messages_are_delivered_without_loss():
    result = run(SimulationConfig(nodes=6, events_per_node=100, seed=11))
    receives = [e for e in result.events if e.event_type is EventType.RECEIVE]

    assert result.lost_messages == 0
    assert len(receives) == len(result.messages)


def test_loss_probability_drops_messages_and_removes_receives():
    config = SimulationConfig(nodes=6, events_per_node=200, loss_probability=0.5, seed=5)
    result = run(config)
    receives = [e for e in result.events if e.event_type is EventType.RECEIVE]

    assert 0 < result.lost_messages < len(result.messages)
    assert len(receives) == len(result.delivered_message_ids)


def test_zero_message_probability_yields_a_purely_local_execution():
    result = run(SimulationConfig(nodes=4, events_per_node=25, message_probability=0.0, seed=9))

    assert result.messages == []
    assert all(e.event_type is EventType.LOCAL for e in result.events)


def test_delivery_never_precedes_its_send_in_physical_time():
    result = run(SimulationConfig(nodes=8, events_per_node=150, seed=13))
    by_id = result.events_by_id

    for event in result.events:
        if event.event_type is EventType.RECEIVE:
            send_id = next(d for d in event.dependencies if by_id[d].node_id != event.node_id)
            assert by_id[send_id].physical_time <= event.physical_time


@pytest.mark.parametrize("topology", ["ring", "star", "random", "scale_free"])
def test_messages_only_travel_along_topology_edges(topology):
    config = SimulationConfig(nodes=8, events_per_node=100, topology=topology, seed=17)
    neighbours = build_neighbourhoods(topology, config.nodes, config.seed)
    result = run(config)

    assert result.messages
    for message in result.messages:
        assert message.receiver in neighbours[message.sender]


def test_config_rejects_unknown_keys():
    with pytest.raises(ValueError):
        SimulationConfig.from_dict({"nodes": 4, "events_per_node": 10, "bogus": 1})


def test_config_rejects_degenerate_sizes():
    with pytest.raises(ValueError):
        SimulationConfig(nodes=1, events_per_node=10)
    with pytest.raises(ValueError):
        SimulationConfig(nodes=4, events_per_node=0)


def test_node_failures_drop_messages_in_flight_to_the_failed_node():
    config = SimulationConfig(
        nodes=6,
        events_per_node=300,
        failure_probability=0.02,
        mean_failure_duration=20.0,
        seed=27,
    )
    result = run(config)

    assert result.failures > 0
    assert result.total_downtime > 0
    assert result.messages_dropped_by_failure > 0
    assert result.messages_dropped_by_network == 0


def test_failed_nodes_resume_their_pending_work_after_recovery():
    config = SimulationConfig(
        nodes=5,
        events_per_node=200,
        failure_probability=0.05,
        mean_failure_duration=15.0,
        seed=33,
    )
    result = run(config)

    steps = [sum(1 for e in result.events if e.node_id == n and e.event_type is not EventType.RECEIVE) for n in range(config.nodes)]
    assert steps == [config.events_per_node] * config.nodes


def test_clocks_survive_a_failure_and_stay_monotone_on_each_node():
    config = SimulationConfig(
        nodes=5,
        events_per_node=200,
        failure_probability=0.05,
        mean_failure_duration=15.0,
        seed=34,
    )
    result = run(config)

    for node_id in range(config.nodes):
        stamps = [e.lamport_timestamp for e in result.events if e.node_id == node_id]
        assert stamps == sorted(stamps)
        assert len(set(stamps)) == len(stamps)


def test_loss_and_failure_account_for_every_undelivered_message():
    config = SimulationConfig(
        nodes=6,
        events_per_node=300,
        loss_probability=0.1,
        failure_probability=0.01,
        mean_failure_duration=20.0,
        seed=37,
    )
    result = run(config)

    assert result.messages_dropped_by_network > 0
    assert result.messages_dropped_by_failure > 0
    assert result.messages_dropped_by_network + result.messages_dropped_by_failure == result.lost_messages


def test_failure_configuration_requires_a_duration():
    with pytest.raises(ValueError):
        SimulationConfig(nodes=4, events_per_node=10, failure_probability=0.1)
    with pytest.raises(ValueError):
        SimulationConfig(nodes=4, events_per_node=10, failure_probability=1.0)
