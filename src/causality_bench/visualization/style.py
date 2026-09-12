from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

FIGURE_DIR = Path("results/figures")

SURFACE = "#fcfcfb"
PRIMARY_INK = "#0b0b0b"
SECONDARY_INK = "#52514e"
MUTED_INK = "#898781"
GRIDLINE = "#e1e0d9"
AXIS_LINE = "#c3c2b7"

# categorical slots are assigned in a fixed order and never cycled
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")
LAMPORT, VECTOR = SERIES[0], SERIES[1]

# ordered levels use a single hue stepped light to dark
ORDINAL_BLUE = ("#86b6ef", "#3987e5", "#256abf", "#104281")

CAPTION_WIDTH = 110


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "figure.dpi": 200,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "axes.facecolor": SURFACE,
            "axes.edgecolor": AXIS_LINE,
            "axes.linewidth": 0.8,
            "axes.labelcolor": SECONDARY_INK,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "axes.titlecolor": PRIMARY_INK,
            "axes.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRIDLINE,
            "grid.linewidth": 0.6,
            "grid.linestyle": "-",
            "text.color": PRIMARY_INK,
            "xtick.color": MUTED_INK,
            "ytick.color": MUTED_INK,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "xtick.labelcolor": SECONDARY_INK,
            "ytick.labelcolor": SECONDARY_INK,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "lines.linewidth": 1.8,
            "lines.markersize": 5,
            "font.family": "sans-serif",
            "font.size": 9,
        }
    )


def save_figure(fig: plt.Figure, name: str, caption: str, directory: Path = FIGURE_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    fig.text(
        0.0,
        -0.02,
        textwrap.fill(caption, CAPTION_WIDTH),
        ha="left",
        va="top",
        fontsize=7.5,
        color=SECONDARY_INK,
    )

    path = directory / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path
