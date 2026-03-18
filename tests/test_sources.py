"""Tests for jflow data sources."""

import json
from pathlib import Path

import pytest

from jflow.sources import CsvSource, ExcelSource, FileResult, FileSource


# ── FileResult ───────────────────────────────────────────────────────────


class TestFileResult:
    def test_existing_file(self, tmp_path):
        p = tmp_path / "hello.txt"
        p.write_text("hello world")
        r = FileResult(p)
        assert r.exists is True
        assert bool(r) is True
        assert r.content == "hello world"
        assert r.name == "hello.txt"
        assert r.stem == "hello"
        assert r.path == p
        assert str(r) == "hello world"

    def test_missing_file(self):
        r = FileResult(None)
        assert r.exists is False
        assert bool(r) is False
        assert r.content == ""
        assert r.name == ""
        assert r.stem == ""
        assert r.path is None

    def test_data_json(self, tmp_path):
        p = tmp_path / "meta.json"
        p.write_text(json.dumps({"version": 2, "tags": ["a", "b"]}))
        r = FileResult(p)
        assert r.data["version"] == 2
        assert r.data["tags"][0] == "a"

    def test_data_yaml(self, tmp_path):
        p = tmp_path / "cfg.yaml"
        p.write_text("version: 3\nname: test\n")
        r = FileResult(p)
        assert r.data["version"] == 3

    def test_data_none_for_txt(self, tmp_path):
        p = tmp_path / "readme.md"
        p.write_text("# Hello")
        r = FileResult(p)
        assert r.data is None

    def test_data_malformed_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{broken")
        r = FileResult(p)
        with pytest.raises(json.JSONDecodeError):
            _ = r.data

    def test_data_missing_file(self):
        r = FileResult(None)
        assert r.data is None


# ── FileSource ───────────────────────────────────────────────────────────


@pytest.fixture
def doc_tree(tmp_path):
    """Create a small directory tree for FileSource tests."""
    (tmp_path / "alpha_spec.md").write_text("alpha spec")
    (tmp_path / "beta_spec.md").write_text("beta spec")
    (tmp_path / "readme.txt").write_text("readme")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.md").write_text("deep file")
    return tmp_path


class TestFileSource:
    def test_find_exact(self, doc_tree):
        fs = FileSource(doc_tree)
        r = fs.find("alpha_spec.md")
        assert r.exists
        assert r.content == "alpha spec"

    def test_find_glob(self, doc_tree):
        fs = FileSource(doc_tree)
        r = fs.find("*_spec.md")
        assert r.exists
        assert r.name == "alpha_spec.md"  # sorted, alpha first

    def test_find_missing(self, doc_tree):
        fs = FileSource(doc_tree)
        r = fs.find("nonexistent.md")
        assert not r.exists

    def test_list_all(self, doc_tree):
        fs = FileSource(doc_tree)
        results = fs.list("*.md")
        names = [r.name for r in results]
        assert "alpha_spec.md" in names
        assert "beta_spec.md" in names

    def test_list_default(self, doc_tree):
        fs = FileSource(doc_tree)
        results = fs.list()
        assert len(results) >= 3  # alpha, beta, readme (not sub dir contents)

    def test_recursive(self, doc_tree):
        fs = FileSource(doc_tree, recursive=True)
        results = fs.list("*.md")
        names = [r.name for r in results]
        assert "deep.md" in names

    def test_not_recursive(self, doc_tree):
        fs = FileSource(doc_tree, recursive=False)
        results = fs.list("*.md")
        names = [r.name for r in results]
        assert "deep.md" not in names


# ── ExcelSource ──────────────────────────────────────────────────────────


@pytest.fixture
def excel_file(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["product_id", "name", "category"])
    ws.append([1, "WidgetA", "hardware"])
    ws.append([2, "WidgetB", "software"])
    p = tmp_path / "products.xlsx"
    wb.save(p)
    return p


class TestExcelSource:
    def test_iterate(self, excel_file):
        src = ExcelSource(excel_file)
        rows = list(src)
        assert len(rows) == 2
        assert rows[0].name == "WidgetA"
        assert rows[1].category == "software"

    def test_headers(self, excel_file):
        src = ExcelSource(excel_file)
        assert src.headers == ["product_id", "name", "category"]

    def test_rows(self, excel_file):
        src = ExcelSource(excel_file)
        assert len(src.rows) == 2

    def test_lookup_found(self, excel_file):
        src = ExcelSource(excel_file)
        row = src.lookup("product_id", 2)
        assert row["name"] == "WidgetB"

    def test_lookup_not_found(self, excel_file):
        src = ExcelSource(excel_file)
        row = src.lookup("product_id", 99)
        assert row == {}


# ── CsvSource ────────────────────────────────────────────────────────────


@pytest.fixture
def csv_file(tmp_path):
    p = tmp_path / "items.csv"
    p.write_text("id,name,price\n1,Apple,1.5\n2,Banana,0.75\n")
    return p


class TestCsvSource:
    def test_iterate(self, csv_file):
        src = CsvSource(csv_file)
        rows = list(src)
        assert len(rows) == 2
        assert rows[0].name == "Apple"

    def test_headers(self, csv_file):
        src = CsvSource(csv_file)
        assert src.headers == ["id", "name", "price"]

    def test_lookup(self, csv_file):
        src = CsvSource(csv_file)
        row = src.lookup("id", "2")
        assert row["name"] == "Banana"

    def test_delimiter(self, tmp_path):
        p = tmp_path / "semi.csv"
        p.write_text("a;b\n1;2\n")
        src = CsvSource(p, delimiter=";")
        rows = list(src)
        assert rows[0]["a"] == "1"
        assert rows[0]["b"] == "2"
