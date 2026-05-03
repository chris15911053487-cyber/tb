import json
import tempfile
from pathlib import Path
from exporter import Exporter


def test_export_json_creates_file():
    data = {"projects": [{"name": "测试项目", "tasks": []}]}
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "output.json")
        Exporter.to_json(data, out)
        with open(out, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data


def test_export_json_nested_dir():
    data = {"key": "val"}
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "sub" / "nested" / "out.json")
        Exporter.to_json(data, out)
        with open(out, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data


def test_export_json_handles_non_string_values():
    from datetime import datetime
    data = {"ts": datetime(2026, 5, 3, 12, 0, 0)}
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "out.json")
        Exporter.to_json(data, out)
        with open(out, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert "2026-05-03" in loaded["ts"]


def test_export_csv_basic():
    rows = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "out.csv")
        Exporter.to_csv(rows, out)
        content = Path(out).read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "name,age" in lines[0] or "age,name" in lines[0]
        assert "Alice" in content
        assert "Bob" in content


def test_export_csv_empty_rows():
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "empty.csv")
        Exporter.to_csv([], out)
        content = Path(out).read_text()
        assert content == ""


def test_export_csv_with_explicit_columns():
    rows = [
        {"a": 1, "b": 2, "c": 3},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "out.csv")
        Exporter.to_csv(rows, out, columns=["a", "c"])
        content = Path(out).read_text()
        lines = content.strip().split("\n")
        assert "a,c" in lines[0]
        assert "1,3" in lines[1]
