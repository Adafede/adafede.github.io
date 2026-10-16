"""talkmap.py robustness.

This module is invoked by talks.qmd on every Quarto render, so a geocoding
failure aborts a build and a markup-bearing title reaches the served popup.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import pytest
from geopy import Nominatim
from geopy.exc import (
    GeocoderQuotaExceeded,
    GeocoderRateLimited,
    GeocoderTimedOut,
    GeocoderUnavailable,
    GeopyError,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.utilities.talkmap import (
    GeoCache,
    create_popup_html,
    geocode_location,
)


class _Cache(GeoCache):
    """A GeoCache whose `set` calls are recorded.

    Subclassed rather than stubbed: geocode_location is typed against GeoCache,
    and a hand-written stand-in is a type error a type checker is right to
    raise.
    """

    def __init__(self, tmp_path: Path, cached: dict | None = None) -> None:
        super().__init__(tmp_path / "geocache.json")
        self.cache = cached or {}
        self.stored: list[tuple[str, float, float, str]] = []

    def set(
        self,
        location: str,
        latitude: float,
        longitude: float,
        address: str,
    ) -> None:
        self.stored.append((location, latitude, longitude, address))
        super().set(location, latitude, longitude, address)


class _Raiser:
    """A geocoder whose geocode() raises, standing in for a Nominatim failure."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def geocode(self, location: str):
        raise self.error


def _failing_geocoder(error: Exception) -> Nominatim:
    """A _Raiser where geocode_location expects a Nominatim.

    The type is a lie the test needs: a real Nominatim cannot be made to raise
    a chosen exception, and building one needs network configuration.
    """
    return cast(Nominatim, _Raiser(error))


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(GeocoderQuotaExceeded("quota"), id="quota"),
        pytest.param(GeocoderRateLimited("rate"), id="rate-limited"),
        pytest.param(GeocoderUnavailable("down"), id="unavailable"),
        pytest.param(GeocoderTimedOut("slow"), id="timeout"),
    ],
)
def test_a_geocoding_failure_is_reported_not_raised(
    error: GeopyError,
    tmp_path: Path,
):
    """A single bad location used to abort the whole map build.

    It escaped geocode_location (which only caught AttributeError/TypeError) and
    escaped extract_talks_metadata (which catches OSError/AttributeError/
    ValueError), so nothing was mapped and cache.save() never ran.
    """
    cache = _Cache(tmp_path)

    assert (
        geocode_location("Zürich, Switzerland", _failing_geocoder(error), cache) is None
    )
    assert cache.stored == []


def test_the_cache_short_circuits_the_geocoder(tmp_path: Path):
    """A cached location must not cost an API call or a rate-limit sleep."""
    cache = _Cache(
        tmp_path,
        {
            "Zürich, Switzerland": {
                "latitude": 47.4,
                "longitude": 8.5,
                "address": "Zürich",
            },
        },
    )

    assert geocode_location(
        "Zürich, Switzerland",
        _failing_geocoder(Exception("must not be called")),
        cache,
    ) == (47.4, 8.5)


def test_the_popup_escapes_markup_bearing_metadata():
    """title/venue/date were interpolated into HTML verbatim."""
    html = create_popup_html(
        {
            "title": "A <script>alert(1)</script> & B",
            "venue": "x < y",
            "date": "2024",
        },
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
    assert "Venue: x &lt; y" in html


def test_a_missing_title_gets_a_placeholder_not_the_word_None():
    assert "No title" in create_popup_html({})
    assert "None" not in create_popup_html({})
