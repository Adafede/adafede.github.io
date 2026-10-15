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

    Both directions of the same mistake are here: one id claimed by two files,
    which is an organisation and its group sharing an id, and one organisation
    carrying several ids, which is an institution split by institute. Both are
    reported at build time and neither is merged, because which is right is a
    statement about the paper, not about the data.

    A new collision fails this test rather than joining the list silently.
    """
    from scripts.site.migrate_posts import (
        duplicate_affiliation_ids,
        split_affiliation_ids,
    )

    # No affiliation id is claimed twice. `iocb` used to be, for the Pluskal
    # and Vondrasek groups of one institute; the two now have their own ids, so
    # that case moved from this list to the one below.
    shared = {
        identifier: sorted(files)
        for identifier, files, _ in duplicate_affiliation_ids()
    }
    assert shared == {}

    split = {tuple(sorted(ids)) for ids in split_affiliation_ids().values()}
    assert split == {
        ("fsu_jena", "fsu_jena_b"),
        ("frankfurt", "frankfurt2"),
        ("iocb_p", "iocb_v"),
        ("ucsd", "ucsd_gen"),
    }


def test_no_author_points_at_a_missing_affiliation():
    """Every `ref` resolves, so no author renders with no affiliation.

    `ulaberta` in DavidWishart_UALBERTA.yml was one: a typo for `ualberta` that
    produced an author with no institution and no indication why.
    """
    from scripts.site.migrate_posts import unresolved_affiliation_refs

    assert unresolved_affiliation_refs() == {}
