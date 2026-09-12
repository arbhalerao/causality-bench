import numpy as np
import pandas as pd
import pytest

from causality_bench.experiments.statistics import (
    confidence_interval,
    log_log_slope,
    paired_comparison,
    summarize,
    write_processed,
)
from causality_bench.provenance import read_csv


@pytest.fixture
def frame():
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        [
            {
                "nodes": nodes,
                "seed": seed,
                "cheap": 100.0 + rng.normal(0, 1),
                "costly": 100.0 * nodes + rng.normal(0, 1),
            }
            for nodes in (2, 4, 8)
            for seed in range(20)
        ]
    )


def test_interval_brackets_the_sample_mean():
    sample = [1.0, 2.0, 3.0, 4.0, 5.0]
    low, high = confidence_interval(sample)

    assert low < np.mean(sample) < high


def test_interval_narrows_as_the_sample_grows():
    rng = np.random.default_rng(1)
    small = confidence_interval(rng.normal(size=10))
    large = confidence_interval(rng.normal(size=1000))

    assert (large[1] - large[0]) < (small[1] - small[0])


def test_interval_is_undefined_for_a_single_observation():
    assert all(np.isnan(bound) for bound in confidence_interval([1.0]))


def test_summary_reports_location_spread_and_interval(frame):
    summary = summarize(frame, ["nodes"], ["costly"])

    assert len(summary) == 3
    assert list(summary["seeds"]) == [20, 20, 20]
    assert {
        "costly_mean",
        "costly_median",
        "costly_std",
        "costly_ci_low",
        "costly_ci_high",
    } <= set(summary.columns)


def test_summary_means_match_a_direct_group_average(frame):
    summary = summarize(frame, ["nodes"], ["costly"]).set_index("nodes")
    expected = frame.groupby("nodes")["costly"].mean()

    assert np.allclose(summary["costly_mean"], expected)


def test_summary_intervals_contain_their_means(frame):
    summary = summarize(frame, ["nodes"], ["costly"])

    assert (summary["costly_ci_low"] < summary["costly_mean"]).all()
    assert (summary["costly_mean"] < summary["costly_ci_high"]).all()


def test_paired_comparison_recovers_the_known_ratio(frame):
    comparison = paired_comparison(frame, ["nodes"], "cheap", "costly").set_index("nodes")

    assert comparison.loc[8, "ratio_ci_low"] < 8.0 < comparison.loc[8, "ratio_ci_high"]
    assert (comparison["p_value"] < 1e-6).all()


def test_paired_comparison_finds_no_difference_between_a_column_and_itself(frame):
    comparison = paired_comparison(frame, ["nodes"], "cheap", "cheap")

    assert np.allclose(comparison["difference_mean"], 0.0)


def test_log_log_slope_recovers_an_exact_power_law():
    frame = pd.DataFrame({"x": [1, 2, 4, 8, 16], "y": [1, 4, 16, 64, 256]})
    fit = log_log_slope(frame, "x", "y")

    assert fit["slope"] == pytest.approx(2.0)
    assert fit["r_squared"] == pytest.approx(1.0)
    assert fit["slope_ci_low"] <= 2.0 <= fit["slope_ci_high"]


def test_log_log_slope_is_flat_for_a_constant_metric():
    frame = pd.DataFrame({"x": [1, 2, 4, 8], "y": [7.0, 7.0, 7.0, 7.0]})
    assert log_log_slope(frame, "x", "y")["slope"] == pytest.approx(0.0)


def test_processed_tables_round_trip_through_csv(frame, tmp_path):
    summary = summarize(frame, ["nodes"], ["costly"])
    path = write_processed(summary, "unit", tmp_path)

    assert path.exists()
    assert len(read_csv(path)) == len(summary)
