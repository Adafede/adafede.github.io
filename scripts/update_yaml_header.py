import re
import yaml
from pathlib import Path

from .make_date import make_date
from .make_doi import make_doi


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

    # Only proceed if no DOI is assigned
    if "doi" in data:
        return

    changed = False
    date_str = make_date(post_path)
    if data.get("date") != date_str:
        data["date"] = date_str
        changed = True

    # Add DOI since it doesn't exist
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
