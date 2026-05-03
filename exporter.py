"""数据导出：JSON / CSV。"""
import csv
import json
from pathlib import Path


class Exporter:
    @staticmethod
    def to_json(data, filepath):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def to_csv(rows, filepath, columns=None):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            return
        columns = columns or list(rows[0].keys())
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
