import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load(name):
    with open(DATA_DIR / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def load_all(map_name="map01"):
    return load("towers"), load("enemies"), load(map_name)
