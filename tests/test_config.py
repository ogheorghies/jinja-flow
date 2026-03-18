"""Tests for jflow config loading and validation."""

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from jflow.config import ConfigError, load_config


@pytest.fixture
def tmp_config(tmp_path):
    """Write a YAML config and return its path."""

    def _write(cfg: dict | str) -> Path:
        p = tmp_path / "config.yaml"
        if isinstance(cfg, str):
            p.write_text(dedent(cfg))
        else:
            p.write_text(yaml.dump(cfg))
        return p

    return _write


class TestValidConfig:
    def test_sources_parsed(self, tmp_config, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "products.xlsx").touch()
        (tmp_path / "docs").mkdir()

        cfg = tmp_config(
            """\
            sources:
              products: { type: excel, file: data/products.xlsx, sheet: Sheet1 }
              docs:     { type: files, path: ./docs, recursive: true }
            renders:
              - template: |-
                  hello
            """
        )
        config = load_config(cfg)
        assert "products" in config.sources
        assert "docs" in config.sources
        assert config.sources["products"].type == "excel"
        assert config.sources["products"].sheet == "Sheet1"
        assert config.sources["docs"].recursive is True

    def test_csv_source(self, tmp_config, tmp_path):
        (tmp_path / "data.csv").touch()
        cfg = tmp_config(
            """\
            sources:
              items: { type: csv, file: data.csv, delimiter: ";", encoding: latin-1 }
            renders:
              - template: |-
                  hello
            """
        )
        config = load_config(cfg)
        assert config.sources["items"].delimiter == ";"
        assert config.sources["items"].encoding == "latin-1"

    def test_render_with_for(self, tmp_config, tmp_path):
        (tmp_path / "data.csv").touch()
        cfg = tmp_config(
            """\
            sources:
              items: { type: csv, file: data.csv }
            renders:
              - template: |-
                  {{ item.name }}
                for: { items: item }
            """
        )
        config = load_config(cfg)
        assert config.renders[0].for_clause is not None
        assert config.renders[0].for_clause.source == "items"
        assert config.renders[0].for_clause.var == "item"

    def test_render_with_for_and_join(self, tmp_config, tmp_path):
        (tmp_path / "data.csv").touch()
        cfg = tmp_config(
            """\
            sources:
              items: { type: csv, file: data.csv }
            renders:
              - template: |-
                  {{ item.name }}
                for: { items: item, join: "\\n---\\n" }
            """
        )
        config = load_config(cfg)
        assert config.renders[0].for_clause.join == "\n---\n"

    def test_file_template_resolved(self, tmp_config, tmp_path):
        (tmp_path / "data.csv").touch()
        cfg = tmp_config(
            """\
            sources:
              items: { type: csv, file: data.csv }
            renders:
              - template: prompts/analyze.j2
                for: { items: item }
            """
        )
        config = load_config(cfg)
        assert config.renders[0].template == str(tmp_path / "prompts" / "analyze.j2")
        assert config.renders[0].template_is_inline is False

    def test_inline_template(self, tmp_config, tmp_path):
        cfg = tmp_config(
            """\
            sources: {}
            renders:
              - template: |-
                  line one
                  line two
            """
        )
        config = load_config(cfg)
        assert config.renders[0].template_is_inline is True
        assert "line one" in config.renders[0].template

    def test_relative_paths(self, tmp_config, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "data.xlsx").touch()
        cfg = tmp_config(
            """\
            sources:
              items: { type: excel, file: sub/data.xlsx }
            renders:
              - template: |-
                  hello
            """
        )
        config = load_config(cfg)
        assert config.sources["items"].file == tmp_path / "sub" / "data.xlsx"


class TestValidationErrors:
    def test_jinja_output_without_for(self, tmp_config):
        cfg = tmp_config(
            """\
            sources: {}
            renders:
              - template: |-
                  hello
                output: "outputs/{{ item.name }}.txt"
            """
        )
        with pytest.raises(ConfigError, match="Jinja expression.*requires 'for'"):
            load_config(cfg)

    def test_for_undeclared_source(self, tmp_config):
        cfg = tmp_config(
            """\
            sources: {}
            renders:
              - template: |-
                  hello
                for: { missing: item }
            """
        )
        with pytest.raises(ConfigError, match="undeclared source.*missing"):
            load_config(cfg)

    def test_for_files_source(self, tmp_config, tmp_path):
        (tmp_path / "docs").mkdir()
        cfg = tmp_config(
            """\
            sources:
              docs: { type: files, path: ./docs }
            renders:
              - template: |-
                  hello
                for: { docs: item }
            """
        )
        with pytest.raises(ConfigError, match="cannot iterate over 'files'"):
            load_config(cfg)

    def test_unknown_source_type(self, tmp_config):
        cfg = tmp_config(
            """\
            sources:
              x: { type: unknown }
            renders: []
            """
        )
        with pytest.raises(ConfigError, match="unknown type"):
            load_config(cfg)

    def test_missing_template(self, tmp_config):
        cfg = tmp_config(
            """\
            sources: {}
            renders:
              - output: out.txt
            """
        )
        with pytest.raises(ConfigError, match="'template' is required"):
            load_config(cfg)

    def test_excel_missing_file(self, tmp_config):
        cfg = tmp_config(
            """\
            sources:
              x: { type: excel }
            renders: []
            """
        )
        with pytest.raises(ConfigError, match="'file' is required"):
            load_config(cfg)

    def test_files_missing_path(self, tmp_config):
        cfg = tmp_config(
            """\
            sources:
              x: { type: files }
            renders: []
            """
        )
        with pytest.raises(ConfigError, match="'path' is required"):
            load_config(cfg)
