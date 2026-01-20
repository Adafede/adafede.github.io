"""PDF service for Pandoc PDF generation."""

import subprocess
from pathlib import Path
import shutil
import re

from infrastructure.filesystem import FileSystem
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class PdfService:
    """Handles PDF generation using Pandoc."""

    def __init__(
        self,
        filesystem: FileSystem,
        bibliography_file: Path,
        csl_file: Path,
        filters: list[Path],
    ):
        """Initialize PDF service.

        Args:
            filesystem: FileSystem instance
            bibliography_file: Path to bibliography file
            csl_file: Path to CSL style file
            filters: List of Lua filter paths
        """
        self.fs = filesystem
        self.bibliography_file = bibliography_file
        self.csl_file = csl_file
        self.filters = filters

    def _fix_image_paths_in_md(self, md_path: Path) -> None:
        """Rewrite Markdown image paths that start with '../images/' to '_site/images/...'

        Only performs the rewrite when the target file exists under the
        repository `_site/images` directory to avoid creating broken links.

        This edits the file in-place and saves a `.bak` backup if changes are made.
        """
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception:
            logger.debug(f"Could not read {md_path} for path-fix")
            return

        # Replace any Markdown image references of the form: ![alt](../images/...) -> ![alt](_site/images/...)
        md_img_pattern = (
            r"!\[([^\]]*)\]\(\s*\.\./images/([^\)\s]+)(?:\s+\"[^\"]*\")?\s*\)"
        )
        new_text, n = re.subn(md_img_pattern, r"![\1](_site/images/\2)", text)

        if n > 0 and new_text != text:
            bak = md_path.with_suffix(md_path.suffix + ".bak")
            try:
                shutil.copy2(md_path, bak)
            except Exception:
                logger.warning(f"Could not create backup for {md_path}")
            try:
                md_path.write_text(new_text, encoding="utf-8")
                logger.info(f"Rewrote {n} Markdown image path(s) in {md_path}")
            except Exception as e:
                logger.error(f"Failed to write fixed markdown {md_path}: {e}")
        else:
            logger.debug(f"No Markdown image path fixes required for {md_path}")

    def convert_md_to_pdf(
        self,
        md_path: Path,
        pdf_path: Path,
    ) -> bool:
        """Convert markdown file to PDF using Pandoc.

        Args:
            md_path: Path to markdown file
            pdf_path: Path for output PDF

        Returns:
            True if successful
        """
        if not self.fs.exists(md_path):
            logger.warning(f"Markdown file not found: {md_path}")
            return False

        # Attempt to fix image paths in generated markdown (rewrites ../images -> _site/images when present)
        try:
            self._fix_image_paths_in_md(md_path)
        except Exception as e:
            logger.debug(f"Image path fix failed for {md_path}: {e}")

        # Build Pandoc command
        cmd = self._build_pandoc_command(md_path, pdf_path)

        logger.debug(f"Running: {' '.join(str(c) for c in cmd)}")

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=str(self.fs.root),
            )
            logger.info(f"✓ Generated PDF: {pdf_path.name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Pandoc failed for {md_path.name}: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("Pandoc not found. Please install Pandoc.")
            return False

    def _build_pandoc_command(
        self,
        md_path: Path,
        pdf_path: Path,
    ) -> list[str]:
        """Build Pandoc command with all filters and options.

        Args:
            md_path: Input markdown path
            pdf_path: Output PDF path

        Returns:
            Command as list of strings
        """
        cmd = [
            "pandoc",
            str(md_path),
            "--to=pdf",
        ]

        # Add bibliography if exists
        if self.fs.exists(self.bibliography_file):
            cmd.append(f"--bibliography={self.bibliography_file}")

        # Add filters (pre-citeproc)
        for filter_path in self.filters[: len(self.filters) // 2]:
            if self.fs.exists(filter_path):
                cmd.append(f"--lua-filter={filter_path}")

        # Add citeproc
        cmd.append("--citeproc")

        # Add filters (post-citeproc)
        for filter_path in self.filters[len(self.filters) // 2 :]:
            if self.fs.exists(filter_path):
                cmd.append(f"--lua-filter={filter_path}")

        # Add CSL if exists
        if self.fs.exists(self.csl_file):
            cmd.append(f"--csl={self.csl_file}")

        # Add output
        cmd.extend(["-o", str(pdf_path)])

        return cmd

    def process_qmd_files(
        self,
        qmd_files: list[Path],
        site_dir: Path,
    ) -> int:
        """Process QMD files to generate PDFs.

        Args:
            qmd_files: List of QMD source files
            site_dir: Site output directory

        Returns:
            Number of PDFs successfully generated
        """
        logger.info(f"Processing {len(qmd_files)} QMD files for PDF generation")

        generated = 0
        failed = 0

        for qmd_path in qmd_files:
            # Find corresponding markdown file in _site
            md_path = site_dir / qmd_path.parent.name / f"{qmd_path.stem}.md"

            if not self.fs.exists(md_path):
                logger.debug(f"Markdown not found for {qmd_path.name}, skipping PDF")
                continue

            # Output PDF path
            pdf_path = site_dir / qmd_path.parent.name / f"{qmd_path.stem}.pdf"

            # Convert to PDF
            if self.convert_md_to_pdf(md_path, pdf_path):
                generated += 1
            else:
                failed += 1

        logger.info(f"PDF generation complete: {generated} succeeded, {failed} failed")
        return generated

    def process_cv(
        self,
        cv_qmd_path: Path,
        output_pdf_path: Path,
        template: Path | None = None,
    ) -> bool:
        """Process CV QMD file with custom template.

        Args:
            cv_qmd_path: Path to CV QMD file
            output_pdf_path: Path for output PDF
            template: Optional LaTeX template path

        Returns:
            True if successful
        """
        if not self.fs.exists(cv_qmd_path):
            logger.warning(f"CV QMD not found: {cv_qmd_path}")
            return False

        cmd = [
            "pandoc",
            str(cv_qmd_path),
            "--to=pdf",
        ]

        if template and self.fs.exists(template):
            cmd.append(f"--template={template}")

        cmd.extend(["-o", str(output_pdf_path)])

        logger.debug(f"Running CV conversion: {' '.join(cmd)}")

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=str(self.fs.root),
            )
            logger.info(f"✓ Generated CV PDF: {output_pdf_path.name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ CV PDF generation failed: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("Pandoc not found.")
            return False
