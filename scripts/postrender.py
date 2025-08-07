import glob
import os

from convert_rss_to_json_feed import convert_rss_to_json_feed
from inject_cito_annotations_in_html import inject_cito_annotations_in_html
from inject_cito_annotations_in_rss import inject_cito_annotations_in_rss
from inject_doi_in_rss import inject_doi_in_rss
from merge_citos import merge_citos
from parse_citos_from_qmd import parse_citos_from_qmd
from run_pandoc_for_all_qmds import run_pandoc_for_all_qmds


def postrender():
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
        inject_doi_in_rss(
            rss_path=rss_path,
            qmd_files=qmd_files,
        )
        inject_cito_annotations_in_rss(
            rss_path=rss_path,
            citation_properties=citation_properties,
        )

        # Convert RSS to JSON Feed format
        json_feed_path = "_site/posts.json"
        convert_rss_to_json_feed(rss_path=rss_path, json_feed_path=json_feed_path)

    else:
        print(f"RSS file not found at {rss_path}")


if __name__ == "__main__":
    postrender()
