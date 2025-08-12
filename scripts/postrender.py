import glob
import os
from pathlib import Path

from .convert_rss_to_json_feed import convert_rss_to_json_feed
from .inject_cito_annotations_in_html import inject_cito_annotations_in_html
from .inject_cito_annotations_in_rss import inject_cito_annotations_in_rss
from .inject_doi_in_rss import inject_doi_in_rss
from .inject_ror_in_html import inject_ror_in_html
from .merge_citos import merge_citos
from .parse_citos_from_qmd import parse_citos_from_qmd
from .process_qmd_directory import process_qmd_directory
from .run_pandoc_for_all_qmds import run_pandoc_for_all_qmds


def postrender():
    # Run Pandoc conversion once
    run_pandoc_for_all_qmds()

    # === ARTICLES ===
    process_qmd_directory(qmd_glob="articles/**/*.qmd")

    # === TALKS ===
    process_qmd_directory(qmd_glob="talks/*.qmd")

    # === TEACHING ===
    process_qmd_directory(qmd_glob="teaching/*.qmd")

    # === POSTS ===
    post_qmds = glob.glob("posts/*.qmd")

    # Parse and merge CiTO annotations
    all_cito_dicts = [parse_citos_from_qmd(qmd) for qmd in post_qmds]
    citation_properties = {k: sorted(v) for k, v in merge_citos(all_cito_dicts).items()}

    # Inject CiTO + ROR into HTML files
    for qmd_file in post_qmds:
        base = os.path.splitext(os.path.basename(qmd_file))[0]
        html_file = os.path.join("_site", "posts", base + ".html")

        if os.path.isfile(html_file):
            inject_cito_annotations_in_html(
                html_path=html_file,
                citation_properties=citation_properties,
            )
            inject_ror_in_html(
                qmd_path=Path(qmd_file),
                html_path=Path(html_file),
            )
        else:
            print(f"[WARN] HTML not found for {qmd_file} at {html_file}")

    # === RSS / JSON FEED ===
    rss_path = "_site/posts.xml"
    if os.path.isfile(rss_path):
        inject_doi_in_rss(rss_path=rss_path, qmd_files=post_qmds)
        inject_cito_annotations_in_rss(
            rss_path=rss_path,
            citation_properties=citation_properties,
        )

        # Convert to JSON Feed
        convert_rss_to_json_feed(
            rss_path=rss_path,
            json_feed_path="_site/posts.json",
        )
    else:
        print(f"[WARN] RSS file not found at {rss_path}")


if __name__ == "__main__":
    postrender()
