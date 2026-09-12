from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from causality_bench.simulation.topology import Neighbourhood, Topology, build_neighbourhoods


class DelayDistribution(str, Enum):
    DETERMINISTIC = "deterministic"
    UNIFORM = "uniform"
    EXPONENTIAL = "exponential"


# uniform delays are drawn from [mean * (1 - spread), mean * (1 + spread)]
UNIFORM_SPREAD = 0.9


@dataclass
class Network:
    """
    message transport with a fixed topology, a delay law, and independent loss
    all three distributions are parameterised by the same mean so that changing the delay law varies only the variance of the transport
    """

    neighbourhoods: Neighbourhood
    delay_distribution: DelayDistribution
    mean_delay: float
    loss_probability: float = 0.0

    @classmethod
    def build(
        cls,
        node_count: int,
        topology: Topology | str,
        delay_distribution: DelayDistribution | str,
        mean_delay: float,
        seed: int,
        loss_probability: float = 0.0,
    ) -> Network:
        return cls(
            neighbourhoods=build_neighbourhoods(topology, node_count, seed),
            delay_distribution=DelayDistribution(delay_distribution),
            mean_delay=mean_delay,
            loss_probability=loss_probability,
        )

    def neighbours(self, node_id: int) -> tuple[int, ...]:
        return self.neighbourhoods[node_id]

    def sample_delay(self, rng: np.random.Generator) -> float:
        if self.delay_distribution is DelayDistribution.DETERMINISTIC:
            return self.mean_delay
        if self.delay_distribution is DelayDistribution.UNIFORM:
            low = self.mean_delay * (1.0 - UNIFORM_SPREAD)
            high = self.mean_delay * (1.0 + UNIFORM_SPREAD)
            return float(rng.uniform(low, high))
        return float(rng.exponential(self.mean_delay))

    def drops(self, rng: np.random.Generator) -> bool:
        # always consume a draw so that delay streams stay aligned across loss settings
        return rng.random() < self.loss_probability
