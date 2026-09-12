import pytest

from causality_bench.clocks import LamportClock


@pytest.fixture
def clock():
    return LamportClock(node_id=0)


def test_starts_at_zero(clock):
    assert clock.snapshot() == 0


def test_local_events_increment_monotonically(clock):
    assert [clock.tick() for _ in range(3)] == [1, 2, 3]


def test_send_advances_and_returns_stamped_time(clock):
    clock.tick()
    assert clock.send() == 2
    assert clock.snapshot() == 2


def test_receive_from_ahead_takes_remote_plus_one(clock):
    clock.tick()
    assert clock.receive(remote_time=9) == 10


def test_receive_from_behind_advances_local(clock):
    for _ in range(5):
        clock.tick()
    assert clock.receive(remote_time=2) == 6


def test_receive_equal_time_still_advances(clock):
    clock.tick()
    assert clock.receive(remote_time=1) == 2


def test_repeated_messages_never_decrease_time(clock):
    stamps = [clock.receive(remote_time=r) for r in (7, 3, 7, 1, 12)]
    assert stamps == sorted(stamps)
    assert stamps == [8, 9, 10, 11, 13]


def test_send_receive_pair_orders_causally():
    sender, receiver = LamportClock(node_id=0), LamportClock(node_id=1)
    for _ in range(4):
        receiver.tick()

    sent = sender.send()
    delivered = receiver.receive(sent)

    assert sent < delivered
