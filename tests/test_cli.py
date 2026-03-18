"""End-to-end CLI tests for jflow."""

import subprocess
import sys
from pathlib import Path

import pytest


def run_jflow(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "jflow", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestCLI:
    def test_no_args(self):
        r = run_jflow()
        assert r.returncode == 1
        assert "Usage" in r.stderr

    def test_file_not_found(self, tmp_path):
        r = run_jflow("nonexistent.yaml", cwd=tmp_path)
        assert r.returncode == 1
        assert "file not found" in r.stderr

    def test_invalid_config(self, tmp_path):
        cfg = tmp_path / "bad.yaml"
        cfg.write_text(
            "sources:\n  x: { type: unknown }\nrenders: []\n"
        )
        r = run_jflow(str(cfg), cwd=tmp_path)
        assert r.returncode == 1
        assert "Config error" in r.stderr

    def test_undefined_variable(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "sources: {}\n"
            "renders:\n"
            "  - template: |-\n"
            "      {{ missing_var }}\n"
        )
        r = run_jflow(str(cfg), cwd=tmp_path)
        assert r.returncode == 1
        assert "Template error" in r.stderr

    def test_end_to_end_stdout(self, tmp_path):
        (tmp_path / "items.csv").write_text("name,color\nApple,red\nBanana,yellow\n")
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "sources:\n"
            "  items: { type: csv, file: items.csv }\n"
            "renders:\n"
            "  - template: |-\n"
            "      {% for item in items %}{{ item.name }}: {{ item.color }}\n"
            "      {% endfor %}\n"
        )
        r = run_jflow(str(cfg), cwd=tmp_path)
        assert r.returncode == 0
        assert "Apple: red" in r.stdout
        assert "Banana: yellow" in r.stdout

    def test_end_to_end_output_files(self, tmp_path):
        (tmp_path / "items.csv").write_text("name\nAlpha\nBeta\n")
        out_dir = tmp_path / "out"
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "sources:\n"
            "  items: { type: csv, file: items.csv }\n"
            "renders:\n"
            "  - template: |-\n"
            "      Hello {{ item.name }}\n"
            "    for: { items: item }\n"
            f"    output: \"{out_dir}/{{{{ item.name }}}}.txt\"\n"
        )
        r = run_jflow(str(cfg), cwd=tmp_path)
        assert r.returncode == 0
        assert (out_dir / "Alpha.txt").read_text() == "Hello Alpha"
        assert (out_dir / "Beta.txt").read_text() == "Hello Beta"
