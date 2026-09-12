from __future__ import annotations

from dataclasses import dataclass

from causality_bench.clocks import LamportClock, Vector, VectorClock


@dataclass(frozen=True, slots=True)
class ClockMetadata:
    """clock state piggybacked on a message"""

    lamport: int
    vector: Vector

    def lamport_bytes(self) -> int:
        return LamportClock.timestamp_bytes(len(self.vector))

    def vector_bytes(self) -> int:
        return VectorClock.timestamp_bytes(len(self.vector))


@dataclass(frozen=True, slots=True)
class Message:
    message_id: int
    sender: int
    receiver: int
    send_time: float
    delivery_time: float
    clock_metadata: ClockMetadata
    send_event_id: int
