"""Post and author domain models."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Affiliation:
    """Represents an institutional affiliation."""

    name: str
    ror: Optional[str] = None
    qid: Optional[str] = None  # Wikidata QID

    @property
    def ror_url(self) -> Optional[str]:
        """Get full ROR URL."""
        if self.ror:
            return f"https://ror.org/{self.ror}"
        return None

    @property
    def wikidata_url(self) -> Optional[str]:
        """Get Wikidata URL."""
        if self.qid:
            return f"https://www.wikidata.org/wiki/{self.qid}"
        return None

    @property
    def scholia_url(self) -> Optional[str]:
        """Get Scholia organization URL."""
        if self.qid:
            return f"https://scholia.toolforge.org/organization/{self.qid}"
        return None


@dataclass
class Author:
    """Represents a document author."""

    name: str
    orcid: Optional[str] = None
    affiliations: list[Affiliation] = field(default_factory=list)
    email: Optional[str] = None
    url: Optional[str] = None

    @property
    def orcid_url(self) -> Optional[str]:
        """Get full ORCID URL."""
        if self.orcid:
            return f"https://orcid.org/{self.orcid}"
        return None


@dataclass
class Post:
    """Represents a blog post or article."""

    path: Path
    title: Optional[str] = None
    date: Optional[str] = None
    doi: Optional[str] = None
    authors: list[Author] = field(default_factory=list)
    abstract: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def slug(self) -> str:
        """Get post slug (filename without extension)."""
        return self.path.stem

    @property
    def doi_url(self) -> Optional[str]:
        """Get full DOI URL."""
        if self.doi:
            if self.doi.startswith("http"):
                return self.doi
            return f"https://doi.org/{self.doi}"
        return None

    @property
    def date_from_filename(self) -> str:
        """Extract date from filename (YYYY-MM-DD prefix)."""
        return self.path.stem.split("_")[0]

    def get_html_path(self, site_dir: Path) -> Path:
        """Get corresponding HTML output path."""
        # Assuming posts are in posts/ directory
        html_name = self.path.stem + ".html"
        return site_dir / "posts" / html_name
