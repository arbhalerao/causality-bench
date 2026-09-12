from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from causality_bench.provenance import write_csv

CONFIDENCE = 0.95
DEFAULT_PROCESSED_DIR = Path("results/processed")


def confidence_interval(values: Sequence[float], confidence: float = CONFIDENCE) -> tuple[float, float]:
    """two-sided Student-t interval for the mean of independent seed replicates"""
    sample = np.asarray(values, dtype=float)
    n = sample.size
    if n < 2:
        return (float("nan"), float("nan"))

    half_width = stats.t.ppf(0.5 + confidence / 2, df=n - 1) * sample.std(ddof=1) / np.sqrt(n)
    mean = float(sample.mean())
    return (mean - half_width, mean + half_width)


def summarize(
    frame: pd.DataFrame,
    group_by: Sequence[str],
    metrics: Sequence[str],
    confidence: float = CONFIDENCE,
) -> pd.DataFrame:
    """per-configuration location, spread, and interval across independent seeds"""
    rows = []
    for key, group in frame.groupby(list(group_by), sort=True):
        record = dict(zip(group_by, key if isinstance(key, tuple) else (key,), strict=True))
        record["seeds"] = len(group)

        for metric in metrics:
            values = group[metric]
            low, high = confidence_interval(values, confidence)
            record[f"{metric}_mean"] = float(values.mean())
            record[f"{metric}_median"] = float(values.median())
            record[f"{metric}_std"] = float(values.std(ddof=1)) if len(values) > 1 else float("nan")
            record[f"{metric}_ci_low"] = low
            record[f"{metric}_ci_high"] = high

        rows.append(record)

    return pd.DataFrame(rows)


def paired_comparison(
    frame: pd.DataFrame,
    group_by: Sequence[str],
    baseline: str,
    treatment: str,
    confidence: float = CONFIDENCE,
) -> pd.DataFrame:
    """compare two measurements taken from the same runs

    both clocks are driven by one execution per seed, so the two columns are
    matched observations rather than independent samples; the paired difference
    removes the between-seed variance that both share
    """
    rows = []
    for key, group in frame.groupby(list(group_by), sort=True):
        record = dict(zip(group_by, key if isinstance(key, tuple) else (key,), strict=True))
        difference = group[treatment].to_numpy(float) - group[baseline].to_numpy(float)
        ratio = group[treatment].to_numpy(float) / group[baseline].to_numpy(float)
        low, high = confidence_interval(difference, confidence)
        ratio_low, ratio_high = confidence_interval(ratio, confidence)
        test = stats.ttest_rel(group[treatment], group[baseline])

        record.update(
            {
                "seeds": len(group),
                "baseline_mean": float(group[baseline].mean()),
                "treatment_mean": float(group[treatment].mean()),
                "difference_mean": float(difference.mean()),
                "difference_ci_low": low,
                "difference_ci_high": high,
                "ratio_mean": float(ratio.mean()),
                "ratio_ci_low": ratio_low,
                "ratio_ci_high": ratio_high,
                "t_statistic": float(test.statistic),
                "p_value": float(test.pvalue),
            }
        )
        rows.append(record)

    return pd.DataFrame(rows)


def log_log_slope(
    frame: pd.DataFrame,
    x: str,
    metric: str,
    confidence: float = CONFIDENCE,
) -> dict[str, float]:
    """fit metric ~ x^slope on the seed-level observations

    the slope is the empirical scaling exponent and is reported next to, never in
    place of, the analytic complexity of the operation
    """
    subset = frame[[x, metric]].astype(float)
    subset = subset[(subset[x] > 0) & (subset[metric] > 0)]
    fit = stats.linregress(np.log2(subset[x]), np.log2(subset[metric]))

    half_width = stats.t.ppf(0.5 + confidence / 2, df=len(subset) - 2) * fit.stderr
    return {
        "metric": metric,
        "slope": float(fit.slope),
        "slope_ci_low": float(fit.slope - half_width),
        "slope_ci_high": float(fit.slope + half_width),
        "r_squared": float(fit.rvalue**2),
        "observations": len(subset),
    }


def write_processed(frame: pd.DataFrame, name: str, directory: Path = DEFAULT_PROCESSED_DIR) -> Path:
    return write_csv(frame, directory / f"{name}.csv", source="experiments/run_analysis.py")
