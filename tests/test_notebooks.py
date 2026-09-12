import json
from pathlib import Path

import pytest

NOTEBOOKS = sorted((Path(__file__).parent.parent / "notebooks").glob("*.ipynb"))
RESULTS = Path(__file__).parent.parent / "results" / "processed"

needs_results = pytest.mark.skipif(
    not RESULTS.exists(),
    reason="no generated results; run `make generate`",
)


def code_cells(path: Path) -> list[str]:
    document = json.loads(path.read_text())
    return ["".join(cell["source"]) for cell in document["cells"] if cell["cell_type"] == "code"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_is_valid_json_with_cells(path):
    """a null or duplicate cell id makes nbconvert refuse the file, so make discard fails"""
    document = json.loads(path.read_text())
    assert document["cells"]

    ids = [cell.get("id") for cell in document["cells"]]
    assert all(isinstance(i, str) and i for i in ids), f"missing or null cell id: {ids}"
    assert len(set(ids)) == len(ids), f"duplicate cell ids: {ids}"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_committed_outputs_are_in_execution_order(path):
    """
    outputs are committed so the notebooks read on their own, which only helps
    if they came from one top-to-bottom run rather than cells fired piecemeal
    """
    document = json.loads(path.read_text())
    counts = [cell["execution_count"] for cell in document["cells"] if cell["cell_type"] == "code" and cell.get("execution_count") is not None]
    assert counts == sorted(counts), f"cells were run out of order: {counts}"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_no_cell_recorded_an_error(path):
    document = json.loads(path.read_text())
    for cell in document["cells"]:
        for output in cell.get("outputs", []):
            assert output.get("output_type") != "error", output.get("ename")


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_carries_no_embedded_images(path):
    """tables are cheap to store; base64 plots are not, and they belong in results/figures"""
    document = json.loads(path.read_text())
    for cell in document["cells"]:
        for output in cell.get("outputs", []):
            assert not [k for k in output.get("data", {}) if k.startswith("image/")]


@needs_results
@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_runs(path, monkeypatch, capsys):
    monkeypatch.chdir(path.parent)
    namespace: dict = {"__name__": "__main__"}

    for source in code_cells(path):
        exec(compile(source, str(path), "exec"), namespace)

    capsys.readouterr()
