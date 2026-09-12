from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LamportClock:
    """scalar logical clock following Lamport (1978)"""

    node_id: int
    time: int = 0

    def tick(self) -> int:
        """advance for a local event"""
        self.time += 1
        return self.time

    def send(self) -> int:
        """advance and return the timestamp carried by the outgoing message"""
        self.time += 1
        return self.time

    def receive(self, remote_time: int) -> int:
        self.time = max(self.time, remote_time) + 1
        return self.time

    def snapshot(self) -> int:
        return self.time

    @staticmethod
    def timestamp_bytes(node_count: int) -> int:
        """one 64-bit counter regardless of system size"""
        return 8
