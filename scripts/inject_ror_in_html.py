import re
import yaml
from pathlib import Path


def inject_ror_in_html(qmd_path: Path, html_path: Path):
    if not qmd_path.exists() or not html_path.exists():
        return

    content = qmd_path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        return

    yaml_data = yaml.safe_load(match.group(1))
    all_affiliations = yaml_data.get("affiliations", [])

    aff_dict = {}
    for aff in all_affiliations:
        aff_id = aff.get("id")
        name = aff.get("name")
        ror = aff.get("ror")
        if aff_id and name and ror:
            aff_dict[name.strip()] = ror.strip()

    ror_icon_url = "https://raw.githubusercontent.com/ror-community/ror-logos/refs/heads/main/ror-icon-rgb-transparent.svg"

    html = html_path.read_text()

    affiliation_patt = re.compile(
        r'(<p class="affiliation">\s*(.*?)\s*</p>)',
        re.DOTALL,
    )

    def repl(match):
        full_tag = match.group(1)
        aff_text = match.group(2).strip()
        if aff_text in aff_dict:
            ror_url = aff_dict[aff_text]
            new_tag = (
                f'<p class="affiliation">{aff_text} '
                f'<a class="uri" href="{ror_url}">'
                f'<img src="{ror_icon_url}" style="height:14px; vertical-align:middle;" alt="ROR logo">'
                f"</a></p>"
            )
            return new_tag
        else:
            print(f"[!] ROR ID not found in YAML: {aff_text}")
            return full_tag

    html = affiliation_patt.sub(repl, html)

    html_path.write_text(html)
