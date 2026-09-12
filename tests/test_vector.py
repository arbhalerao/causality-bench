import pytest

from causality_bench.clocks import VectorClock, concurrent, happens_before, identical


def test_initialises_to_zero_vector():
    assert VectorClock(node_id=1, node_count=3).snapshot() == (0, 0, 0)


def test_rejects_mismatched_initial_vector():
    with pytest.raises(ValueError):
        VectorClock(node_id=0, node_count=3, times=[0, 0])


def test_tick_advances_only_the_owning_entry():
    clock = VectorClock(node_id=1, node_count=3)
    assert clock.tick() == (0, 1, 0)
    assert clock.tick() == (0, 2, 0)


def test_receive_merges_pointwise_maximum_then_ticks():
    clock = VectorClock(node_id=1, node_count=3, times=[1, 4, 7])
    assert clock.receive((5, 2, 3)) == (5, 5, 7)


def test_receive_rejects_wrong_length():
    with pytest.raises(ValueError):
        VectorClock(node_id=0, node_count=3).receive((1, 1))


def test_equal_vectors_are_neither_ordered_nor_concurrent():
    a = (2, 3, 1)
    assert identical(a, a)
    assert not happens_before(a, a)
    assert not concurrent(a, a)


def test_happens_before_and_its_reverse():
    a, b = (1, 0, 0), (2, 1, 0)
    assert happens_before(a, b)
    assert not happens_before(b, a)
    assert not concurrent(a, b)


def test_concurrent_vectors_are_incomparable():
    a, b = (2, 0, 0), (0, 3, 0)
    assert concurrent(a, b)
    assert not happens_before(a, b)
    assert not happens_before(b, a)


def test_dominating_in_one_entry_only_is_still_ordered():
    assert happens_before((1, 1, 1), (1, 1, 2))


def test_message_chain_across_three_nodes_is_totally_ordered():
    a, b, c = (VectorClock(node_id=i, node_count=3) for i in range(3))

    first = a.send()
    second = b.receive(first)
    third = c.receive(second)

    assert happens_before(first, second)
    assert happens_before(second, third)
    assert happens_before(first, third)


def test_independent_nodes_produce_concurrent_stamps():
    a, b = VectorClock(node_id=0, node_count=2), VectorClock(node_id=1, node_count=2)

    left = a.tick()
    right = b.tick()

    assert concurrent(left, right)


def test_events_before_a_message_are_ordered_before_events_after_it():
    sender = VectorClock(node_id=0, node_count=2)
    receiver = VectorClock(node_id=1, node_count=2)

    before_send = sender.tick()
    unrelated = receiver.tick()
    receiver.receive(sender.send())
    after_receive = receiver.tick()

    assert happens_before(before_send, after_receive)
    assert concurrent(before_send, unrelated)


def test_comparison_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        happens_before((1, 0), (1, 0, 0))
