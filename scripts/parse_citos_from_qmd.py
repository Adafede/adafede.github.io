import re
from collections import defaultdict

citation_pattern = re.compile(r"\[@([^\]]+)\]")


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
