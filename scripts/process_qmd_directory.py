import glob
import os
from pathlib import Path

from inject_ror_in_html import inject_ror_in_html


def process_qmd_directory(qmd_glob: str):
    root_dir = qmd_glob.split("*", 1)[0].rstrip("/")

    qmd_files = glob.glob(qmd_glob, recursive=True)
    for qmd_file in qmd_files:
        rel_path = os.path.relpath(qmd_file, root_dir)
        rel_html_path = os.path.splitext(rel_path)[0] + ".html"
        html_file = os.path.join("_site", root_dir, rel_html_path)

        if os.path.isfile(html_file):
            inject_ror_in_html(Path(qmd_file), Path(html_file))
        else:
            print(f"[WARN] HTML not found for {qmd_file} at {html_file}")
