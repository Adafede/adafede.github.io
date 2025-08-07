import glob
import os
import re
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
