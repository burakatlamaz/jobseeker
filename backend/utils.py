import json
from pathlib import Path
from typing import Any


def ensure_directories(paths: list[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def read_jsonl_file(file_path: Path) -> list[dict]:
    rows = []

    with file_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            clean_line = line.strip()

            if not clean_line:
                continue

            try:
                row = json.loads(clean_line)
                rows.append(row)
            except json.JSONDecodeError as error:
                print(f"[WARN] Could not parse {file_path.name} line {line_number}: {error}")

    return rows


def read_json_file(file_path: Path) -> Any:
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json_file(file_path: Path, data: Any) -> None:
    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False, sort_keys=False)