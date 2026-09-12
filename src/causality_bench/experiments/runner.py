from __future__ import annotations

import itertools
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from causality_bench.experiments.metrics import evaluate
from causality_bench.simulation.simulator import SimulationConfig, run

DEFAULT_RAW_DIR = Path("results/raw")


@dataclass(frozen=True)
class ExperimentSpec:
    """one controlled experiment: a base configuration, a sweep, and seeds"""

    name: str
    base: dict[str, Any]
    seeds: tuple[int, ...]
    sweep: dict[str, list[Any]] = field(default_factory=dict)
    benchmark_repetitions: int = 3000
    description: str = ""

    @classmethod
    def from_yaml(cls, path: str | Path) -> ExperimentSpec:
        document = yaml.safe_load(Path(path).read_text())
        return cls(
            name=document["name"],
            base=document.get("base", {}),
            seeds=_expand_seeds(document["seeds"]),
            sweep=document.get("sweep", {}) or {},
            benchmark_repetitions=document.get("benchmark_repetitions", 3000),
            description=document.get("description", ""),
        )

    def configs(self) -> Iterator[SimulationConfig]:
        keys = list(self.sweep)
        combinations = itertools.product(*(self.sweep[key] for key in keys)) if keys else [()]

        for values in combinations:
            for seed in self.seeds:
                settings = dict(self.base)
                settings.update(dict(zip(keys, values, strict=True)))
                settings["seed"] = seed
                yield SimulationConfig.from_dict(settings)

    def __len__(self) -> int:
        widths = [len(values) for values in self.sweep.values()]
        combinations = 1
        for width in widths:
            combinations *= width
        return combinations * len(self.seeds)


def run_experiment(spec: ExperimentSpec, progress: bool = True) -> pd.DataFrame:
    """
    execute every configuration in the sweep sequentially

    runs are not parallelised: the record carries wall-clock timings, and
    running configurations concurrently would contaminate them with contention
    """
    records = []
    total = len(spec)

    for index, config in enumerate(spec.configs(), start=1):
        record = evaluate(run(config), repetitions=spec.benchmark_repetitions)
        record["experiment"] = spec.name
        records.append(record)

        if progress:
            print(f"\r{spec.name}: {index}/{total}", end="", file=sys.stderr, flush=True)

    if progress:
        print(file=sys.stderr)

    return pd.DataFrame.from_records(records)


def save_raw(frame: pd.DataFrame, name: str, raw_dir: Path = DEFAULT_RAW_DIR) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{name}.csv"
    frame.to_csv(path, index=False)
    return path


def execute(spec_path: str | Path, raw_dir: Path = DEFAULT_RAW_DIR) -> Path:
    spec = ExperimentSpec.from_yaml(spec_path)
    return save_raw(run_experiment(spec), spec.name, raw_dir)


def _expand_seeds(value: Any) -> tuple[int, ...]:
    if isinstance(value, list):
        return tuple(int(seed) for seed in value)
    start, count = int(value["start"]), int(value["count"])
    return tuple(range(start, start + count))
