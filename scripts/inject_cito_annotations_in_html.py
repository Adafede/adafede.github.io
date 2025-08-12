from bs4 import BeautifulSoup

from .snake_to_camel_case import snake_to_camel_case


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

        # Transform snake_case properties to camelCase
        camel_case_props = [snake_to_camel_case(prop) for prop in cito_props]
        annotation_text = " ".join(f"[cito:{prop}]" for prop in camel_case_props)

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
