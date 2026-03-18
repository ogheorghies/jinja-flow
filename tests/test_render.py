"""Tests for the jflow render engine."""

from io import StringIO
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from jinja_flow.config import load_config
from jinja_flow.render import render_config
from jinja_flow.sources import CsvSource, FileSource, build_source


def _make_config(tmp_path, cfg_text: str) -> tuple:
    """Write config, build sources, return (config, sources)."""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(dedent(cfg_text))
    config = load_config(cfg_path)
    sources = {}
    for name, sdef in config.sources.items():
        sources[name] = build_source(sdef)
    return config, sources


class TestTemplateIteration:
    def test_inline_template_no_for(self, tmp_path):
        (tmp_path / "items.csv").write_text("name\nAlpha\nBeta\n")
        config, sources = _make_config(
            tmp_path,
            """\
            sources:
              items: { type: csv, file: items.csv }
            renders:
              - template: |-
                  {% for item in items %}{{ item.name }}
                  {% endfor %}
            """,
        )
        out = StringIO()
        render_config(config, sources, stdout=out)
        assert "Alpha" in out.getvalue()
        assert "Beta" in out.getvalue()

    def test_file_template(self, tmp_path):
        (tmp_path / "items.csv").write_text("name\nAlpha\n")
        (tmp_path / "tmpl.j2").write_text("Hello {{ items.rows[0].name }}")
        config, sources = _make_config(
            tmp_path,
            """\
            sources:
              items: { type: csv, file: items.csv }
            renders:
              - template: tmpl.j2
            """,
        )
        out = StringIO()
        render_config(config, sources, stdout=out)
        assert out.getvalue() == "Hello Alpha"


class TestDriverIteration:
    def test_per_row_stdout(self, tmp_path):
        (tmp_path / "items.csv").write_text("name\nA\nB\n")
        config, sources = _make_config(
            tmp_path,
            """\
            sources:
              items: { type: csv, file: items.csv }
            renders:
              - template: |-
                  [{{ item.name }}]
                for: { items: item }
            """,
        )
        out = StringIO()
        render_config(config, sources, stdout=out)
        assert out.getvalue() == "[A][B]"

    def test_per_row_output_files(self, tmp_path):
        (tmp_path / "items.csv").write_text("name\nAlpha\nBeta\n")
        config, sources = _make_config(
            tmp_path,
            """\
            sources:
              items: { type: csv, file: items.csv }
            renders:
              - template: |-
                  Hello {{ item.name }}
                for: { items: item }
                output: "outputs/{{ item.name }}.txt"
            """,
        )
        render_config(config, sources)
        assert (Path("outputs") / "Alpha.txt").read_text() == "Hello Alpha"
        assert (Path("outputs") / "Beta.txt").read_text() == "Hello Beta"
        # cleanup
        import shutil

        shutil.rmtree("outputs")

    def test_join(self, tmp_path):
        (tmp_path / "items.csv").write_text("name\nA\nB\nC\n")
        config, sources = _make_config(
            tmp_path,
            """\
            sources:
              items: { type: csv, file: items.csv }
            renders:
              - template: |-
                  {{ item.name }}
                for: { items: item, join: "---" }
            """,
        )
        out = StringIO()
        render_config(config, sources, stdout=out)
        assert out.getvalue() == "A---B---C"

    def test_join_to_file(self, tmp_path):
        (tmp_path / "items.csv").write_text("name\nX\nY\n")
        out_path = tmp_path / "out.txt"
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            "sources:\n"
            "  items: { type: csv, file: items.csv }\n"
            "renders:\n"
            "  - template: |-\n"
            "      {{ item.name }}\n"
            '    for: { items: item, join: "," }\n'
            f"    output: {out_path}\n"
        )
        config = load_config(cfg_path)
        sources = {n: build_source(s) for n, s in config.sources.items()}
        render_config(config, sources)
        assert out_path.read_text() == "X,Y"


class TestInclude:
    def test_include_partial(self, tmp_path):
        (tmp_path / "items.csv").write_text("name\nAlpha\n")
        (tmp_path / "prompts").mkdir()
        (tmp_path / "prompts" / "header.j2").write_text("== HEADER ==\n")
        config, sources = _make_config(
            tmp_path,
            """\
            sources:
              items: { type: csv, file: items.csv }
            renders:
              - template: |-
                  {% include "prompts/header.j2" %}{{ items.rows[0].name }}
            """,
        )
        out = StringIO()
        render_config(config, sources, stdout=out)
        assert "== HEADER ==" in out.getvalue()
        assert "Alpha" in out.getvalue()


class TestStrictUndefined:
    def test_undefined_raises(self, tmp_path):
        config, sources = _make_config(
            tmp_path,
            """\
            sources: {}
            renders:
              - template: |-
                  {{ nonexistent_var }}
            """,
        )
        from jinja2 import UndefinedError

        with pytest.raises(UndefinedError):
            render_config(config, sources, stdout=StringIO())


class TestOutputDirectoryCreation:
    def test_creates_parent_dirs(self, tmp_path):
        out_path = tmp_path / "deep" / "nested" / "out.txt"
        config, sources = _make_config(
            tmp_path,
            f"""\
            sources: {{}}
            renders:
              - template: |-
                  hello
                output: {out_path}
            """,
        )
        render_config(config, sources)
        assert out_path.read_text() == "hello"
