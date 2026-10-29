from scripts.site.migrate_posts import convert_span_attributes


def test_convert_span_attributes_keeps_rdfa_on_non_link_span():
    body = '[metabolomics]{about="wd:Q12149006"}'

    assert convert_span_attributes(body) == (
        '<span about="wd:Q12149006">metabolomics</span>'
    )


def test_entity_files_hold_one_record_each():
    """One author or affiliation per file.

    `MITE_authors_1.yml` and `MITE.yml` each held dozens, which is what made the
    id collisions below invisible: a shared id is obvious in a directory of
    single-record files and buried in a bundle.
    """
    import pathlib

    import yaml

    entities = pathlib.Path(__file__).resolve().parents[1] / "_includes" / "entities"
    for kind, key in (("authors", "author"), ("affiliations", "affiliations")):
        files = sorted((entities / kind).glob("*.yml"))
        assert files, f"no {kind} entity files found"
        for path in files:
            records = yaml.safe_load(path.read_text())[key]
            assert len(records) == 1, f"{path.name} holds {len(records)} records"


def test_known_affiliation_id_collisions():
    """The id conflations that exist, listed rather than resolved.

    Both directions of the same mistake were here: one id claimed by two files,
    which was `iocb` for the Pluskal and Vondrasek groups of one institute, and
    one organisation split across ids, which was `frankfurt`/`frankfurt2` and
    `fsu_jena`/`fsu_jena_b`. Resolving them by hand rather than in the script is
    the point, so the list is empty and a new collision fails this test instead
    of joining it quietly.
    """
    from scripts.site.migrate_posts import (
        duplicate_affiliation_ids,
        split_affiliation_ids,
    )

    assert duplicate_affiliation_ids() == []
    assert split_affiliation_ids() == {}


def test_entity_machine_names_are_ascii():
    """Filenames, ids and refs are ASCII; prose is not required to be.

    An id, a ref and a filename have to survive a keyboard, a case-sensitive
    filesystem and a shell that does not quote its arguments: `TÜBINGEN.yml`
    and `HellenBertoletiBarbie ri_unicamp_chem.yml` both broke something.

    Display values are left alone, because they are prose. "ETH Zürich" is how
    the institution writes itself, and a transliterated "ETH Zuerich" in an
    address is a different spelling, not a portable one.
    """
    import pathlib

    import yaml

    entities = pathlib.Path(__file__).resolve().parents[1] / "_includes" / "entities"
    for kind, key in (("authors", "author"), ("affiliations", "affiliations")):
        for path in (entities / kind).glob("*.yml"):
            assert path.name.isascii(), f"{path.name} is not ASCII"
            assert " " not in path.name, f"{path.name} contains a space"
            for entry in yaml.safe_load(path.read_text())[key]:
                assert entry["id"].isascii(), f"{entry['id']} is not ASCII"
                for affiliation in entry.get("affiliations") or []:
                    assert affiliation["ref"].isascii(), (
                        f"{affiliation['ref']} is not ASCII"
                    )


def test_affiliation_ids_name_their_unit():
    """`<institution>_<unit>[_<group>]`, and the file name is the id.

    `imsb` said nothing about which institute of ETH it was; `ethz_imsb_zamboni`
    says all three parts. An affiliation with no department and no group keeps
    the bare institution, which is unambiguous only because nothing else claims
    it, so a bare id that appears next to its siblings would fail here.
    """
    import pathlib

    import yaml

    directory = (
        pathlib.Path(__file__).resolve().parents[1]
        / "_includes"
        / "entities"
        / "affiliations"
    )
    records = []
    for path in sorted(directory.glob("*.yml")):
        entry = yaml.safe_load(path.read_text())["affiliations"][0]
        assert path.stem == entry["id"], f"{path.name} is not named after {entry['id']}"
        records.append(entry)

    for entry in records:
        unit = entry.get("department") or entry.get("group")
        if not unit:
            continue
        parts = entry["id"].split("_")
        assert len(parts) > 1, (
            f"{entry['id']} has a department or group but names no unit"
        )


def test_author_file_names_carry_their_affiliation():
    """`<AuthorId>_<affiliation id>[_MULTI][_corr|_eq|_deceased].yml`.

    The name is the only place the distinction between `AdrianoRutz_UNIGE.yml`
    and `AdrianoRutz_IMSB.yml` — one person, two papers, two affiliations —
    survives, so it has to name the affiliation as the id writes it.
    """
    import pathlib

    import yaml

    directory = (
        pathlib.Path(__file__).resolve().parents[1]
        / "_includes"
        / "entities"
        / "authors"
    )
    for path in sorted(directory.glob("*.yml")):
        entry = yaml.safe_load(path.read_text())["author"][0]
        refs = [a["ref"] for a in entry["affiliations"]]
        suffix = "MULTI" if len(refs) > 1 else refs[0]
        for flag, mark in (
            ("correspondence", "_corr"),
            ("corresponding", "_corr"),
            ("equal-contributor", "_eq"),
            ("equalContributor", "_eq"),
            ("deceased", "_deceased"),
        ):
            if entry.get(flag):
                suffix += mark
        assert path.name == f"{entry['id']}_{suffix}.yml", path.name


def test_cv_year_range_reads_the_dashes_the_sources_write():
    """The heading separator is a run of dashes, not a single one.

    Every `cv/` partial spells the range `2015 -- 2016`: a lone `-` is a hyphen
    in Markdown and `--` is what Pandoc's smart extension turns into an en dash.
    The pattern used to accept only one dash at a time, so it matched nothing,
    `endYear` and `current` came back false for every entry, and the CV page
    printed the start year alone — `2015`, with no range at all. It failed
    quietly, because the filename fallback supplies a start year either way.
    """
    from scripts.site.migrate_posts import CV_YEAR_RANGE_RE

    for separator in ("--", "–", "—", "-"):
        match = CV_YEAR_RANGE_RE.match(f"2015 {separator} 2016")
        assert match is not None, f"{separator!r} did not parse"
        assert match.group("from") == "2015"
        assert match.group("to") == "2016"

    ongoing = CV_YEAR_RANGE_RE.match("2022 -- present")
    assert ongoing is not None, "'-- present' did not parse"
    assert ongoing.group("to") == "present"

    assert CV_YEAR_RANGE_RE.match("Swiss National ORD Prize") is None


def test_cv_entries_carry_both_years_of_their_range():
    """Every ranged CV entry keeps its end year and its `present` flag.

    The regression test above covers the pattern; this one runs it over the real
    partials through `parse_cv_entry`, so a source whose range stops parsing
    fails on the data rather than on the regex.

    Awards are excluded deliberately: `### Swiss National ORD Prize (2023)` is a
    single point year, not a range, and `endYear`/`current` are correctly empty.
    """
    import pathlib
    import re

    from scripts.site.migrate_posts import CV_HEADING_RE, parse_cv_entry

    cv_dir = pathlib.Path(__file__).resolve().parents[1] / "cv"
    ranged = []
    for path in sorted(cv_dir.glob("*/*.qmd")):
        heading = path.read_text(encoding="utf-8").lstrip().splitlines()[0]
        match = CV_HEADING_RE.match(heading)
        if not match:
            continue
        date_range = (match.group("range") or "").strip()
        if re.search(r"\d{4}\s*[-‐‑‒–—―]", date_range):
            ranged.append((path, date_range))

    assert ranged, "no ranged CV entries found"

    for path, date_range in ranged:
        # `parse_cv_entry` returns None for an empty file. Every path reaching
        # here has a heading, so None means the file went blank, and that is
        # worth its own message rather than a TypeError three lines down.
        entry = parse_cv_entry(path)
        assert entry is not None, f"{path.name} parsed to nothing"
        assert entry["startYear"] is not None, f"{path.name} lost its start year"
        assert entry["endYear"] is not None or entry["current"], (
            f"{path.name} lost '{date_range}'"
        )


def test_the_bibliography_is_resolved_against_the_project_root(tmp_path, monkeypatch):
    """The bibliography key was gated on a cwd-relative path.

    `Path("posts") / "references.bib"` resolves against whatever directory the
    process was started in, so every post silently lost its bibliography the
    moment the script was invoked from anywhere but the repo root. The build happens to
    run it from the root, which is why it went unnoticed.
    """
    import scripts.site.migrate_posts as migrate

    monkeypatch.chdir(tmp_path)
    frontmatter = migrate.build_frontmatter({"title": "T"}, "slug", "2026-01-01")

    assert frontmatter["bibliography"] == "../../../posts/references.bib"


def test_prune_keeps_tags_but_drops_the_other_empty_values():
    """An entry with no topics is a fact about the entry; every other empty
    value is a field that was never set."""
    from scripts.site.migrate_posts import prune

    assert prune({"tags": [], "venue": "", "doi": None, "authors": []}) == {"tags": []}


def test_the_quarto_pipeline_paths_are_anchored_to_the_project_root():
    """The Quarto-side scripts built their paths relative to the process CWD.

    Quarto runs them with the project root as the working directory, so the
    relative paths resolved by luck and nowhere else: invoked from /tmp they
    produced "Bibliography not found" and handed Pandoc paths that do not exist.
    """
    import importlib

    pandoc = importlib.import_module(
        "scripts.utilities.run_pandoc_for_all_qmds",
    )
    directory = importlib.import_module(
        "scripts.utilities.process_qmd_directory",
    )

    root = pandoc.PROJECT_ROOT
    assert root.is_absolute()
    for path in (
        pandoc.POSTS_DIR,
        pandoc.BIBLIOGRAPHY_FILE,
        pandoc.CSL_FILE,
        *pandoc.PANDOC_FILTERS,
    ):
        assert path.is_absolute(), path
        assert path.exists(), path
    # SITE_POSTS_DIR is generated by the build, not checked at test time
    assert pandoc.SITE_POSTS_DIR.is_absolute()

    assert directory.PROJECT_ROOT == root
