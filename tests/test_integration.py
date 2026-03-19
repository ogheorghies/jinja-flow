"""Integration tests: run each fixture directory end-to-end via CLI."""

import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def discover_fixtures():
    """Find all fixture directories containing a config.yaml and expected.txt."""
    return sorted(
        d.name
        for d in FIXTURES.iterdir()
        if d.is_dir() and (d / "config.yaml").exists() and (d / "expected.txt").exists()
    )


@pytest.mark.parametrize("fixture", discover_fixtures())
def test_fixture(fixture):
    fixture_dir = FIXTURES / fixture
    config = fixture_dir / "config.yaml"
    expected = (fixture_dir / "expected.txt").read_text()

    r = subprocess.run(
        [sys.executable, "-m", "jinja_flow", str(config)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert r.stdout == expected, (
        f"Output mismatch for {fixture}:\n"
        f"--- expected ---\n{expected}\n"
        f"--- got ---\n{r.stdout}"
    )
