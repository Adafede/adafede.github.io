from commonmeta import encode_doi
from pathlib import Path
import yaml
import re


def get_all_posts(post_base: str = "posts") -> list[Path]:
    return list(Path(post_base).glob("20[0-9][0-9]-[01][0-9]-[0-3][0-9]_*.qmd"))


def make_date(path: Path) -> str:
    return path.stem.split("_")[0]


def make_doi() -> str:
    doi_url = encode_doi("10.59350")
    return doi_url.removeprefix("https://doi.org/")


def update_yaml_header(post_path: Path) -> None:
    content = post_path.read_text()
    # Match the YAML front matter
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if match:
        front_matter, body = match.groups()
        data = yaml.safe_load(front_matter) or {}
    else:
        # No existing front matter
        data = {}
        body = content

    changed = False
    date_str = make_date(post_path)
    if data.get("date") != date_str:
        data["date"] = date_str
        changed = True

    if "doi" not in data:
        data["doi"] = make_doi()
        changed = True

    if changed:
        # Custom YAML dumper to maintain proper indentation
        class CustomDumper(yaml.SafeDumper):
            def increase_indent(self, flow=False, indentless=False):
                return super().increase_indent(flow, False)

        new_front = yaml.dump(
            data,
            sort_keys=False,
            allow_unicode=True,
            default_style=None,
            indent=2,
            default_flow_style=False,
            width=float("inf"),
            Dumper=CustomDumper,
        )

        # Replace single quotes with double quotes, but not for date values
        lines = new_front.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("date:"):
                # Remove any quotes from dates
                lines[i] = line.replace('"', "").replace("'", "")
            elif "'" in line:
                lines[i] = line.replace("'", '"')
        new_front = "\n".join(lines)
        new_content = f"---\n{new_front}---\n\n{body.lstrip()}"
        post_path.write_text(new_content)


def update_all_posts(paths: list[Path]) -> None:
    for path in paths:
        update_yaml_header(path)


# Main execution
post_files = get_all_posts("posts")
update_all_posts(post_files)
