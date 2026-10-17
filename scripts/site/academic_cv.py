"""Render the academic CV's publications and talks from Quarto source metadata."""

from __future__ import annotations

import json
import subprocess
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import yaml

Metadata = dict[str, Any]


def _root() -> Path:
    # Anchored to this file rather than the process CWD, so the script resolves
    # the same project root no matter where it is invoked from.
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "_quarto.yml").exists() and (candidate / "talks").is_dir():
        return candidate
    for path in (candidate, *candidate.parents):
        if (path / "_quarto.yml").exists() and (path / "talks").is_dir():
            return path
    raise FileNotFoundError("Could not locate the Quarto project root")


def _frontmatter(path: Path) -> Metadata:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    return yaml.safe_load(text[4:end]) or {}


def _meta(value: Any) -> Any:
    if isinstance(value, list):
        return [_meta(item) for item in value]
    if not isinstance(value, dict):
        return value
    kind, content = value.get("t"), value.get("c")
    if kind is None:
        return {key: _meta(item) for key, item in value.items()}
    if kind == "MetaString":
        return content if isinstance(content, str) else ""
    if kind == "MetaInlines":
        return _inline_text(content if isinstance(content, list) else [])
    if kind == "MetaMap":
        return (
            {key: _meta(item) for key, item in content.items()}
            if isinstance(content, dict)
            else {}
        )
    if kind == "MetaList":
        return [_meta(item) for item in content] if isinstance(content, list) else []
    if kind == "Str":
        return content if isinstance(content, str) else ""
    if kind in ("Space", "SoftBreak", "LineBreak"):
        return " "
    if isinstance(content, (list, dict)):
        return _meta(content)
    return content if content is not None else ""


def _inline_text(items: list[Any]) -> str:
    return "".join(_inline(item) for item in items).strip()


def _inline(item: Metadata) -> str:
    kind, content = item.get("t"), item.get("c")
    if kind == "Str":
        return content if isinstance(content, str) else ""
    if kind in ("Space", "SoftBreak", "LineBreak"):
        return " "
    if kind in ("Emph", "Strong", "SmallCaps", "Quoted"):
        if kind == "Quoted":
            if isinstance(content, list) and len(content) > 1:
                quoted = content[1]
                return _inline_text(quoted) if isinstance(quoted, list) else ""
            return ""
        return _inline_text(content) if isinstance(content, list) else ""
    if (
        kind == "Code"
        and isinstance(content, list)
        and len(content) > 1
        and isinstance(content[1], str)
    ):
        return content[1]
    return ""


def _bibliography(root: Path) -> dict[str, Metadata]:
    references: dict[str, Metadata] = {}
    for path in sorted((root / "articles").glob("**/references.bib")):
        result = subprocess.run(
            ["pandoc", "--from=bibtex", "--to=json", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        document = json.loads(result.stdout)
        for item in _meta(document["meta"]["references"]) or []:
            doi = str(item.get("doi", "")).lower()
            if doi:
                references[doi] = item
    return references


def _person_name(person: Metadata) -> str:
    return " ".join(
        part
        for part in (
            person.get("given"),
            person.get("dropping-particle"),
            person.get("family"),
        )
        if part
    )


def _key(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    return "".join(char for char in decomposed if char.isalnum())


def _contribution_names(source: Path, metadata: Metadata, field: str) -> set[str]:
    names = set(metadata.get(field, []) or [])
    for relative in metadata.get("metadata-files", []) or []:
        path = source.parent / relative
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for author in data.get("author", []) or []:
            if not isinstance(author, dict):
                continue
            if author.get("equal-contributor") and field == "cv-equal-contributors":
                names.add(author.get("name", {}).get("literal", ""))
            if author.get("correspondence") and field == "cv-corresponding-authors":
                names.add(author.get("name", {}).get("literal", ""))
    return {_key(name) for name in names if name}


def _format_authors(
    authors: list[Metadata],
    equal_contributors: set[str],
    corresponding_authors: set[str],
) -> str:
    names = [_person_name(author) for author in authors]
    final_author = _key(names[-1])
    if len(authors) > 6:
        shown: list[Metadata] = authors[:3] + [{"literal": "et al."}]
        shown += [
            author
            for author in authors
            if _key(_person_name(author)) in corresponding_authors | {final_author}
            and author not in authors[:3]
        ]
    else:
        shown = authors

    formatted = []
    for author in shown:
        name = author.get("literal") or _person_name(author)
        key = _key(name)
        if key == _key("et al."):
            formatted.append("et al.")
            continue
        if key == _key("Adriano Rutz"):
            name = f"**{name}**"
        markers = []
        if key in equal_contributors:
            markers.append(r"\dagger")
        if key == final_author:
            markers.append(r"\ddagger")
        if key in corresponding_authors:
            markers.append("*")
        formatted.append(name + (f"$^{{{' '.join(markers)}}}$" if markers else ""))
    return ", ".join(formatted)


def publication_list() -> str:
    root = _root()
    selected = _frontmatter(root / "cv-academic.qmd").get("academic-publications", [])
    references = _bibliography(root)
    entries: list[str] = []

    for relative in selected:
        source = root / relative
        metadata = _frontmatter(source)
        doi = str(metadata["doi"]).lower()
        reference = references[doi]
        authors = _meta(reference["author"])
        if not isinstance(authors, list) or not all(
            isinstance(author, dict) for author in authors
        ):
            raise ValueError(f"Invalid author list in bibliography entry for {doi}")
        equal = _contribution_names(source, metadata, "cv-equal-contributors")
        corresponding = _contribution_names(
            source,
            metadata,
            "cv-corresponding-authors",
        )
        title = _meta(reference["title"])
        journal = _meta(reference.get("container-title", ""))
        year = (
            metadata["date"].year
            if isinstance(metadata["date"], date)
            else str(metadata["date"])[:4]
        )
        entries.append(
            f"{_format_authors(authors, equal, corresponding)}. "
            f"[{title}](https://doi.org/{metadata['doi']}). "
            f"*{journal}*, {year}.",
        )

    return "\n\n".join(entries)


def talk_list() -> str:
    root = _root()
    talks = []
    for source in (root / "talks").glob("*.qmd"):
        metadata = _frontmatter(source)
        categories = metadata.get("categories", []) or []
        if not {"Talk", "Workshop"}.intersection(categories):
            continue
        talk_date = metadata.get("date")
        year = talk_date.year if isinstance(talk_date, date) else str(talk_date)[:4]
        talks.append((str(talk_date), metadata, year))

    talks.sort(key=lambda item: (item[0], item[1].get("title", "")), reverse=True)
    return "\n".join(
        f"- **{year}** — {metadata['title']}; *{metadata['venue']}*"
        + (f" ({metadata['location']})" if metadata.get("location") else "")
        + "."
        for _, metadata, year in talks
    )
