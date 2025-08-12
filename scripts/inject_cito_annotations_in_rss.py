from bs4 import BeautifulSoup
from lxml import etree

from .snake_to_camel_case import snake_to_camel_case


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

            # Transform snake_case properties to camelCase
            camel_case_props = [snake_to_camel_case(prop) for prop in cito_props]
            annotation_text = " ".join(f"[cito:{prop}]" for prop in camel_case_props)

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
