import pandas as pd
import pytest
import yaml

from causality_bench.experiments.runner import ExperimentSpec, run_experiment, save_raw
from causality_bench.provenance import read_csv


def write_spec(tmp_path, document):
    path = tmp_path / "spec.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


@pytest.fixture
def spec_document():
    return {
        "name": "unit",
        "seeds": {"start": 3, "count": 2},
        "base": {"nodes": 3, "events_per_node": 10, "message_probability": 0.3},
        "sweep": {"topology": ["ring", "star"]},
        "benchmark_repetitions": 50,
    }


def test_seed_range_expands_from_start_and_count(tmp_path, spec_document):
    spec = ExperimentSpec.from_yaml(write_spec(tmp_path, spec_document))
    assert spec.seeds == (3, 4)


def test_explicit_seed_list_is_used_verbatim(tmp_path, spec_document):
    spec_document["seeds"] = [11, 13, 17]
    spec = ExperimentSpec.from_yaml(write_spec(tmp_path, spec_document))
    assert spec.seeds == (11, 13, 17)


def test_sweep_expands_to_the_product_of_values_and_seeds(tmp_path, spec_document):
    spec = ExperimentSpec.from_yaml(write_spec(tmp_path, spec_document))
    configs = list(spec.configs())

    assert len(spec) == len(configs) == 4
    assert {(c.topology, c.seed) for c in configs} == {
        ("ring", 3),
        ("ring", 4),
        ("star", 3),
        ("star", 4),
    }


def test_base_settings_apply_to_every_configuration(tmp_path, spec_document):
    spec = ExperimentSpec.from_yaml(write_spec(tmp_path, spec_document))
    assert all(c.nodes == 3 and c.events_per_node == 10 for c in spec.configs())


def test_an_empty_sweep_runs_the_base_configuration_once_per_seed(tmp_path, spec_document):
    spec_document.pop("sweep")
    spec = ExperimentSpec.from_yaml(write_spec(tmp_path, spec_document))
    assert len(list(spec.configs())) == 2


def test_experiment_produces_one_row_per_configuration(tmp_path, spec_document):
    spec = ExperimentSpec.from_yaml(write_spec(tmp_path, spec_document))
    frame = run_experiment(spec, progress=False)

    assert len(frame) == len(spec)
    assert set(frame["experiment"]) == {"unit"}
    assert frame["topology"].tolist() == ["ring", "ring", "star", "star"]


def test_repeated_runs_of_a_spec_reproduce_the_causal_measurements(tmp_path, spec_document):
    spec = ExperimentSpec.from_yaml(write_spec(tmp_path, spec_document))
    columns = ["events", "ordered_pairs", "concurrent_pairs", "lamport_false_orderings"]

    first = run_experiment(spec, progress=False)[columns]
    second = run_experiment(spec, progress=False)[columns]
    pd.testing.assert_frame_equal(first, second)


def test_raw_results_round_trip_through_csv(tmp_path, spec_document):
    spec = ExperimentSpec.from_yaml(write_spec(tmp_path, spec_document))
    frame = run_experiment(spec, progress=False)
    path = save_raw(frame, spec.name, tmp_path / "raw")

    assert path.exists()
    assert len(read_csv(path)) == len(frame)
