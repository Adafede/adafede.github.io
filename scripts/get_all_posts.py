from pathlib import Path


def get_all_posts(post_base: str = "posts") -> list[Path]:
    return list(Path(post_base).glob("20[0-9][0-9]-[01][0-9]-[0-3][0-9]_*.qmd"))
