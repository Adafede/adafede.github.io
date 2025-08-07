from pathlib import Path


def make_date(path: Path) -> str:
    return path.stem.split("_")[0]
