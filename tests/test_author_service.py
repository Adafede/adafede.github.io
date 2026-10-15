"""Author service name matching tests."""

import pytest

from scripts.infrastructure import FileSystem, HtmlProcessor, YamlLoader
from scripts.services.author_service import AuthorService


@pytest.fixture()
def authors_service(tmp_path) -> AuthorService:
    return AuthorService(FileSystem(tmp_path), HtmlProcessor(), YamlLoader())


def _find(
    service: AuthorService,
    author_text: str,
    authors: list[dict[str, str]],
) -> dict[str, str] | None:
    return service._find_author_data(author_text, authors)


def test_exact_match_wins_over_substring_junk(authors_service: AuthorService):
    authors = [
        {"_computed_name": "Emily Li", "orcid": "0000-1"},
        {"_computed_name": "Li", "orcid": "0000-2"},
    ]
    assert _find(authors_service, "Emily Li", authors) == {
        "_computed_name": "Emily Li",
        "orcid": "0000-1",
    }


def test_longer_name_wins_over_shorter_substring(authors_service: AuthorService):
    authors = [
        {"_computed_name": "Li", "orcid": "0000-2"},
        {"_computed_name": "Liang Chen", "orcid": "0000-9"},
    ]
    assert _find(authors_service, "Liang Chen", authors) == {
        "_computed_name": "Liang Chen",
        "orcid": "0000-9",
    }


def test_short_name_is_not_hijacked_by_longer_one(authors_service: AuthorService):
    authors = [
        {"_computed_name": "Emily Li", "orcid": "0000-1"},
        {"_computed_name": "Li", "orcid": "0000-2"},
    ]
    assert _find(authors_service, "Li", authors) == {
        "_computed_name": "Li",
        "orcid": "0000-2",
    }


def test_author_listing_containing_several_names_picks_the_right_one(
    authors_service: AuthorService,
):
    authors = [
        {"_computed_name": "Li", "orcid": "0000-2"},
        {"_computed_name": "Liang Chen", "orcid": "0000-9"},
    ]
    # Rendered as an author listing, the "Li" substring alone must not win.
    assert _find(authors_service, "Li, Liang Chen", authors) == {
        "orcid": "0000-9",
        "_computed_name": "Liang Chen",
    }


def test_no_match_returns_none(authors_service: AuthorService):
    authors = [{"_computed_name": "Emily Li", "orcid": "0000-1"}]
    assert _find(authors_service, "John Smith", authors) is None
