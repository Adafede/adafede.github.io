import glob
import os
import re
from collections import defaultdict
from bs4 import BeautifulSoup
from lxml import etree
import subprocess


citation_pattern = re.compile(r"\[@([^\]]+)\]")


def run_pandoc_for_all_qmds():
    qmd_files = glob.glob("posts/*.qmd")

    for qmd_file in qmd_files:
        base = os.path.splitext(os.path.basename(qmd_file))[0]
        md_path = f"_site/posts/{base}.md"
        pdf_path = f"_site/posts/{base}.pdf"

        if not os.path.isfile(md_path):
            print(f"Skipping {qmd_file}, missing {md_path}")
            continue

        # Construct and run pandoc command
        cmd = [
            "pandoc",
            md_path,
            "--to=pdf",
            "--bibliography=posts/references.bib",
            "--lua-filter=filters/extract-cito.lua",
            "--citeproc",
            "--lua-filter=filters/insert-cito-in-ref.lua",
            "--csl=journal-of-cheminformatics.csl",
            "-o",
            pdf_path,
        ]
        print("Running:", " ".join(cmd))
        try:
            subprocess.run(cmd, check=True)
            print(f"Generated PDF: {pdf_path}")
        except subprocess.CalledProcessError as e:
            print(f"Pandoc failed for {md_path}: {e}")
            continue


def parse_citos_from_qmd(qmd_path):
    citos = defaultdict(set)
    with open(qmd_path, encoding="utf-8") as f:
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
    with open(html_path, encoding="utf-8") as f:
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


def inject_cito_annotations_in_rss(rss_path, citation_properties):
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(rss_path, parser)
    root = tree.getroot()

    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else []

    modified = False
    for item in items:
        desc_elem = item.find("description")
        if desc_elem is None or not desc_elem.text:
            continue

        # Parse the inner HTML with BeautifulSoup
        soup = BeautifulSoup(desc_elem.text, "html.parser")
        refs_container = soup.find("div", id="refs")
        if not refs_container:
            continue

        bib_entries = refs_container.find_all("div", class_="csl-entry")
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
                modified = True

        # Replace the content with a CDATA section explicitly using lxml
        desc_elem.clear()
        desc_elem.text = etree.CDATA(str(soup))

    if modified:
        tree.write(rss_path, pretty_print=True, encoding="utf-8", xml_declaration=True)
        print(f"Injected CiTO annotations into {rss_path}")
    else:
        print(f"No CiTO annotations added to {rss_path}")


def main():
    qmd_files = glob.glob("posts/*.qmd")
    run_pandoc_for_all_qmds()

    all_cito_dicts = [parse_citos_from_qmd(qmd) for qmd in qmd_files]
    citation_properties = merge_citos(all_cito_dicts)
    citation_properties = {k: sorted(v) for k, v in citation_properties.items()}

    # Inject CiTO into all HTML files once
    for qmd_file in qmd_files:
        base = os.path.splitext(os.path.basename(qmd_file))[0]
        html_file = os.path.join("_site", "posts", base + ".html")

        if os.path.isfile(html_file):
            inject_cito_annotations_in_html(
                html_path=html_file,
                citation_properties=citation_properties,
            )
        else:
            print(f"HTML not found for {qmd_file} at {html_file}")

    # Inject CiTO once into RSS after all qmds processed
    rss_path = "_site/posts.xml"
    if os.path.isfile(rss_path):
        inject_cito_annotations_in_rss(
            rss_path=rss_path,
            citation_properties=citation_properties,
        )
    else:
        print(f"RSS file not found at {rss_path}")


if __name__ == "__main__":
    main()
