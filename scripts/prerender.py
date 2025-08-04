from commonmeta import encode_doi
from pathlib import Path
import yaml


def get_all_posts(post_base: str = "posts") -> list[Path]:
    """Get all post files matching posts/YYYY-MM-DD_XXX.qmd

    Args:
        post_base (str, optional): Base post path. Defaults to "posts".

    Returns:
        list[Path]: Paths to post files
    """
    return list(Path(post_base).glob("20[0-9][0-9]-[01][0-9]-[0-3][0-9]_*.qmd"))


def make_metadata(post_path: Path) -> None:
    """Create empty _metadata.yml if it doesn't exist next to post

    Args:
        post_path (Path): Path to post file
    """
    metadata_path = post_path.with_name("_metadata.yml")
    if not metadata_path.exists():
        metadata_path.touch()


def make_all_metadata(paths: list[Path]) -> None:
    """Create _metadata.yml files for all post files

    Args:
        paths (list[Path]): List of post file paths
    """
    for p in paths:
        make_metadata(p)


def make_date(path: Path) -> str:
    """Extract date string from post filename

    Args:
        path (Path): Post file path

    Returns:
        str: Date string (YYYY-MM-DD)
    """
    return path.stem.split("_")[0]


def make_doi() -> str:
    """Generate a DOI

    Returns:
        str: DOI string
    """
    doi_url = encode_doi("10.59350")
    return doi_url.removeprefix("https://doi.org/")


def check_metadata(post_path: Path) -> None:
    """Check and update the _metadata.yml file

    Args:
        post_path (Path): Path to post file
    """
    metadata_path = post_path.with_name("_metadata.yml")
    dat = yaml.safe_load(metadata_path.read_text()) if metadata_path.exists() else None

    if dat is None or not isinstance(dat, dict):
        dat = {}

    changed = False

    date_str = make_date(post_path)
    if dat.get("date") != date_str:
        dat["date"] = date_str
        changed = True

    if "doi" not in dat:
        dat["doi"] = make_doi()
        changed = True

    if changed:
        metadata_path.write_text(yaml.dump(dat))


def check_all_metadata(paths: list[Path]) -> None:
    """Update all metadata files for given post files

    Args:
        paths (list[Path]): List of post file paths
    """
    for p in paths:
        check_metadata(p)


# Main execution
post_files = get_all_posts("posts")
make_all_metadata(post_files)
check_all_metadata(post_files)
