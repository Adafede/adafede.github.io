from pathlib import Path

from update_yaml_header import update_yaml_header


def update_all_posts(paths: list[Path]) -> None:
    for path in paths:
        update_yaml_header(path)
