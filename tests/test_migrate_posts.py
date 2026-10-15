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
