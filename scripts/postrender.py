import glob
import os
import re
from collections import defaultdict
from bs4 import BeautifulSoup

citation_pattern = re.compile(r"\[@([^\]]+)\]")


def parse_citos_from_qmd(qmd_path):
    citos = defaultdict(set)
    with open(qmd_path, "r", encoding="utf-8") as f:
        content = f.read()

    matches = citation_pattern.findall(content)
    for match in matches:
        # The match could be something like "cites:willighagen2024; cites:willighagen2024a; cites:willighagen2025"
        # Split by semicolon to get each citation
        citations = [c.strip() for c in match.split(";")]
        for citation in citations:
            if citation.startswith("@"):
                citation = citation[1:].strip()  # remove leading @ if present

            parts = citation.split(":", 1)
            if len(parts) == 2:
                prop, cite_id = parts
                citos[cite_id].add(prop)
            else:
                cite_id = parts[0]
                citos[cite_id].add("citation")

    return citos


def merge_citos(cito_dicts):
    merged = defaultdict(set)
    for d in cito_dicts:
        for k, v in d.items():
            merged[k].update(v)
    return merged


def inject_cito_annotations_in_html(html_path, citation_properties):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    refs_container = soup.find("div", id="refs")
    if not refs_container:
        print(f"No refs container found in {html_path}")
        return

    bib_entries = refs_container.find_all("div", class_="csl-entry")
    changed = False
    for entry in bib_entries:
        cid = entry.get("id", "")
        if not cid.startswith("ref-"):
            continue
        cite_id = cid[len("ref-") :]

        cito_props = citation_properties.get(cite_id, [])
        if not cito_props:
            continue

        annotation_text = " ".join(f"[cito:{prop}]" for prop in cito_props)

        if not entry.find("span", class_="cito"):
            cito_span = soup.new_tag("span", **{"class": "cito"})
            cito_span.string = " " + annotation_text
            entry.append(cito_span)
            changed = True

    if changed:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(str(soup))
        print(f"Injected CiTO annotations into {html_path}")
    else:
        print(f"No CiTO annotations added to {html_path}")


def main():
    qmd_files = glob.glob("posts/*.qmd")
    all_cito_dicts = []

    for qmd_file in qmd_files:
        citos = parse_citos_from_qmd(qmd_file)
        all_cito_dicts.append(citos)

    citation_properties = merge_citos(all_cito_dicts)

    citation_properties = {k: sorted(v) for k, v in citation_properties.items()}

    for qmd_file in qmd_files:
        base = os.path.splitext(os.path.basename(qmd_file))[0]
        html_file = os.path.join("_site", "posts", base + ".html")

        if os.path.isfile(html_file):
            inject_cito_annotations_in_html(html_file, citation_properties)
        else:
            print(f"HTML not found for {qmd_file} at {html_file}")


if __name__ == "__main__":
    main()
