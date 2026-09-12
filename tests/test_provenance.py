import pandas as pd
import pytest

from causality_bench.experiments.runner import save_raw
from causality_bench.experiments.statistics import write_processed
from causality_bench.provenance import header, png_metadata, read_csv, read_stamp, write_csv


@pytest.fixture
def frame():
    return pd.DataFrame({"nodes": [2, 4, 8], "rate": [0.1, 0.2, 0.3]})


def test_header_names_the_script_that_wrote_the_file():
    assert "source: experiments/run_baseline.py" in header("experiments/run_baseline.py")


def test_header_carries_the_machine_and_the_time():
    text = header("experiments/run_baseline.py")
    assert "machine: " in text
    assert "generated: " in text


def test_every_provenance_line_is_a_comment():
    lines = header("experiments/run_baseline.py").strip().split("\n")
    assert all(line.startswith("#") for line in lines)


def test_a_stamped_csv_round_trips(tmp_path, frame):
    path = write_csv(frame, tmp_path / "scaling.csv", source="experiments/run_scaling.py")

    pd.testing.assert_frame_equal(read_csv(path), frame)


def test_the_stamp_is_readable_back(tmp_path, frame):
    path = write_csv(frame, tmp_path / "scaling.csv", source="experiments/run_scaling.py")

    stamp = read_stamp(path)
    assert stamp["source"] == "experiments/run_scaling.py"
    assert stamp["rows"] == "3"
    assert stamp["generated"].endswith("UTC")


def test_extra_fields_reach_the_stamp(tmp_path, frame):
    path = write_csv(frame, tmp_path / "x.csv", source="s.py", experiment="scaling")

    assert read_stamp(path)["experiment"] == "scaling"


def test_the_data_header_survives_the_stamp(tmp_path, frame):
    path = write_csv(frame, tmp_path / "scaling.csv", source="s.py")

    assert list(read_csv(path).columns) == ["nodes", "rate"]


def test_raw_results_are_stamped_with_their_experiment_script(tmp_path, frame):
    path = save_raw(frame, "scaling", tmp_path)

    assert read_stamp(path)["source"] == "experiments/run_scaling.py"


def test_processed_results_are_stamped_with_the_analysis_script(tmp_path, frame):
    path = write_processed(frame, "scaling_summary", tmp_path)

    assert read_stamp(path)["source"] == "experiments/run_analysis.py"


def test_figure_metadata_uses_the_standard_png_keywords():
    metadata = png_metadata("experiments/make_figures.py", figure="runtime_vs_nodes")

    assert metadata["Software"] == "causality-bench"
    assert metadata["Creation Time"].endswith("UTC")
    assert metadata["figure"] == "runtime_vs_nodes"


def test_an_unstamped_csv_still_reads(tmp_path, frame):
    """files written before provenance existed carry no comment lines"""
    path = tmp_path / "plain.csv"
    frame.to_csv(path, index=False)

    pd.testing.assert_frame_equal(read_csv(path), frame)
