import html
import re
from pathlib import Path
from ruamel.yaml import YAML

def inject_ror_in_html(qmd_path: Path, html_path: Path):
    if not qmd_path.exists() or not html_path.exists():
        return

    qmd_content = qmd_path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", qmd_content, re.DOTALL)
    if not match:
        return

    yaml_loader = YAML(typ="safe")
    try:
        yaml_data = yaml_loader.load(match.group(1))
    except Exception as e:
        print(f"[!] Failed to parse YAML in {qmd_path}: {e}")
        return

    all_affiliations = yaml_data.get("affiliations", [])
    aff_dict = {}
    for aff in all_affiliations:
        aff_id = aff.get("id")
        name = aff.get("name")
        ror = aff.get("ror")
        if aff_id and name and ror:
            aff_dict[name.strip()] = ror.strip()

    ror_icon_url = (
        "https://raw.githubusercontent.com/ror-community/ror-logos/"
        "refs/heads/main/ror-icon-rgb-transparent.svg"
    )

    html_text = html_path.read_text()  # do NOT name this `html` — that would shadow the module

    affiliation_patt = re.compile(
        r'(<p class="affiliation">\s*(.*?)\s*</p>)',
        re.DOTALL,
    )

    def repl(m):
        full_tag = m.group(1)
        inner = m.group(2).strip()

        # if this <p> already contains a ROR link, leave it alone
        if 'class="uri"' in full_tag or 'href="https://ror.org/' in full_tag:
            return full_tag

        # remove any inner HTML tags (anchors/imgs/etc.) to get plain text
        plain = re.sub(r"<[^>]+>", "", inner).strip()
        plain_unescaped = html.unescape(plain)

        if plain_unescaped in aff_dict:
            ror_url = aff_dict[plain_unescaped]
            # keep original escaped/HTML inner text for output, but trimmed
            new_inner = inner
            new_tag = (
                f'<p class="affiliation">{new_inner} '
                f'<a class="uri" href="{ror_url}">'
                f'<img src="{ror_icon_url}" style="height:14px; vertical-align:middle;" alt="ROR logo">'
                f'</a></p>'
            )
            return new_tag
        else:
            print(f"[!] ROR ID not found in YAML: {plain_unescaped}")
            return full_tag

    new_html = affiliation_patt.sub(repl, html_text)
    html_path.write_text(new_html)
