import yaml
from bs4 import BeautifulSoup


def inject_doi_in_rss(rss_path, qmd_files):
    link_to_doi = {}

    for qmd_file in qmd_files:
        with open(qmd_file, encoding="utf-8") as f:
            lines = f.readlines()

        if not lines or lines[0].strip() != "---":
            continue

        yaml_lines = []
        for line in lines[1:]:
            if line.strip() == "---":
                break
            yaml_lines.append(line)

        try:
            metadata = yaml.safe_load("".join(yaml_lines))
        except yaml.YAMLError:
            continue

        if not metadata:
            continue

        title = metadata.get("title")
        doi = metadata.get("doi")

        if title and doi:
            doi = doi.strip()
            # Add prefix if missing
            if not doi.startswith("http"):
                doi = "https://doi.org/" + doi
            link_to_doi[title.strip()] = doi

    # Read and parse RSS XML
    with open(rss_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "xml")

    items = soup.find_all("item")
    for item in items:
        title_tag = item.find("title")
        if not title_tag:
            continue
        title = title_tag.text.strip()
        doi = link_to_doi.get(title)
        if not doi:
            continue

        # Only add DOI if not already present
        existing_doi = item.find("doi")
        if not existing_doi:
            doi_tag = soup.new_tag("doi")
            doi_tag.string = doi
            item.append(doi_tag)

    # Save updated RSS
    with open(rss_path, "w", encoding="utf-8") as f:
        f.write(str(soup))
