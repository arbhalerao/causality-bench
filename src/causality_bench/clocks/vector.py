from __future__ import annotations

from dataclasses import dataclass, field

Vector = tuple[int, ...]


def happens_before(a: Vector, b: Vector) -> bool:
    """a -> b iff a[i] <= b[i] for all i and a[j] < b[j] for some j"""
    if len(a) != len(b):
        raise ValueError("vector timestamps must have the same length")

    # single pass: the pairwise comparison dominates the metrics workload
    strictly_less = False
    for x, y in zip(a, b, strict=True):
        if x > y:
            return False
        if x < y:
            strictly_less = True
    return strictly_less


def concurrent(a: Vector, b: Vector) -> bool:
    return not happens_before(a, b) and not happens_before(b, a) and a != b


def identical(a: Vector, b: Vector) -> bool:
    return tuple(a) == tuple(b)


@dataclass
class VectorClock:
    """per-node vector clock following Fidge (1988) and Mattern (1989)"""

    node_id: int
    node_count: int
    times: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.times:
            self.times = [0] * self.node_count
        elif len(self.times) != self.node_count:
            raise ValueError("vector length must match node count")

    def tick(self) -> Vector:
        self.times[self.node_id] += 1
        return self.snapshot()

    def send(self) -> Vector:
        self.times[self.node_id] += 1
        return self.snapshot()

    def receive(self, remote: Vector) -> Vector:
        if len(remote) != self.node_count:
            raise ValueError("remote vector length must match node count")

        # merge is a pointwise maximum, then the receive itself is a local event
        for i, remote_time in enumerate(remote):
            if remote_time > self.times[i]:
                self.times[i] = remote_time
        self.times[self.node_id] += 1
        return self.snapshot()

    def snapshot(self) -> Vector:
        return tuple(self.times)

    @staticmethod
    def timestamp_bytes(node_count: int) -> int:
        """dense representation: one 64-bit counter per node"""
        return 8 * node_count
