"""Build a self-contained talk map for the Eleventy build.

Quarto produced this with scripts/utilities/talkmap.py, which geocoded every
talk through Nominatim and embedded a Leaflet map. Two things make that a poor
fit for the static build:

  * Nominatim is rate-limited and needs network access, so the map cannot be
    rebuilt deterministically. Geocoding results are cached in
    _cache/geocache.json instead, and the build only uses the cache.
  * Leaflet pulls tiles from a third-party CDN at page load, which costs a
    render-blocking request and shows nothing offline.

So the map is rendered at build time instead: talk locations become markers on
an equirectangular projection over a Natural Earth land outline, with no runtime
dependencies. The outline is by far the largest part of the drawing and carries
fixed colours, so it goes to its own cached file; the markers, which follow the
theme, stay inline. Talks whose location is not in the geocode cache are
reported and skipped rather than silently dropped.

The output is an Eleventy include rather than a standalone page. That is not
just convenience: an iframe resolves `prefers-color-scheme` from the operating
system, while the site lets the reader override the theme with no script, so a
frame would sit light on a dark page (or the reverse). Inlining keeps the map in
the same document, so it follows the same theme and needs no second request.

The land outline is committed at data/world-land.json; refresh it with:

    curl -o data/world-land.json \\
      https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson

Run: uv run python scripts/site/build_talkmap.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "src" / "content" / "talks"
GEOCACHE = ROOT / "_cache" / "geocache.json"
LAND = ROOT / "data" / "world-land.json"
OUT = ROOT / "src" / "eleventy" / "_includes" / "talk-map.njk"
LAND_OUT = ROOT / "src" / "eleventy" / "static" / "talk-map-land.svg"

# The land outline is a "paper map" beige under the theme-styled markers, so its
# colours are fixed and it can live outside the page. Baking them here keeps the
# file self-contained; an inline <path> takes them from CSS instead.
LAND_FILL = "#ded8cd"
LAND_STROKE = "#c6bfb1"
LAND_STROKE_WIDTH = 0.5

# Equirectangular. Cropped tightly to Europe: at a wider extent every
# talk sits in one overlapping cluster near the Alps and the labels collide.
WIDTH, HEIGHT = 960, 480
LON_MIN, LON_MAX = -11.0, 24.0
LAT_MIN, LAT_MAX = 35.0, 56.0


_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)",
    re.DOTALL,
)


def parse_frontmatter(raw: str) -> dict[str, Any]:
    """Parse YAML frontmatter from a Markdown file."""
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return {}
    loaded = yaml.safe_load(match.group(1))
    return loaded if isinstance(loaded, dict) else {}


def city_name(location: str) -> str:
    """The city alone, without the country the heading above it already names."""
    return location.rsplit(",", 1)[0].strip().strip('"')


def project(lon: float, lat: float) -> tuple[float, float]:
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * WIDTH
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * HEIGHT
    return x, y


def _clip_ring(
    pts: list[tuple[float, float]],
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> list[tuple[float, float]]:
    """Sutherland-Hodgman polygon clip against [x_min, x_max] x [y_min, y_max]."""

    def clip_edge(
        poly: list[tuple[float, float]],
        inside: Any,
        intersect: Any,
    ) -> list[tuple[float, float]]:
        if not poly:
            return []
        out: list[tuple[float, float]] = []
        prev = poly[-1]
        prev_in = inside(prev)
        for curr in poly:
            curr_in = inside(curr)
            if curr_in:
                if not prev_in:
                    out.append(intersect(prev, curr))
                out.append(curr)
            elif prev_in:
                out.append(intersect(prev, curr))
            prev, prev_in = curr, curr_in
        return out

    poly = pts
    poly = clip_edge(
        poly,
        lambda p: p[0] >= x_min,
        lambda a, b: (x_min, a[1] + (b[1] - a[1]) * (x_min - a[0]) / (b[0] - a[0])),
    )
    poly = clip_edge(
        poly,
        lambda p: p[0] <= x_max,
        lambda a, b: (x_max, a[1] + (b[1] - a[1]) * (x_max - a[0]) / (b[0] - a[0])),
    )
    poly = clip_edge(
        poly,
        lambda p: p[1] >= y_min,
        lambda a, b: (a[0] + (b[0] - a[0]) * (y_min - a[1]) / (b[1] - a[1]), y_min),
    )
    return clip_edge(
        poly,
        lambda p: p[1] <= y_max,
        lambda a, b: (a[0] + (b[0] - a[0]) * (y_max - a[1]) / (b[1] - a[1]), y_max),
    )


def land_paths() -> str:
    """Land outlines as SVG path data, clipped to the map extent."""
    if not LAND.exists():
        return ""
    features = json.loads(LAND.read_text(encoding="utf-8"))["features"]
    paths = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        polygons = (
            [geometry["coordinates"]]
            if geometry.get("type") == "Polygon"
            else geometry.get("coordinates", [])
        )
        for polygon in polygons:
            for ring in polygon:
                if len(ring) < 3:
                    continue
                points = [project(lon, lat) for lon, lat in ring]
                clipped = _clip_ring(points, -10.0, -10.0, WIDTH + 10.0, HEIGHT + 10.0)
                if len(clipped) < 3:
                    continue
                d = "M" + " ".join(f"{x:.1f},{y:.1f}" for x, y in clipped) + "Z"
                paths.append(d)
    return "".join(paths)


def write_land(d: str) -> None:
    """Write the land outline to its own cached file.

    The outline is one path of a few thousand coordinates; inlined it is parsed
    on every talks page load and re-sent with the document. As a file it is
    downloaded once and cached, and only the markers are left in the page.
    """
    LAND_OUT.parent.mkdir(parents=True, exist_ok=True)
    LAND_OUT.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}">'
        f'<path fill="{LAND_FILL}" stroke="{LAND_STROKE}" '
        f'stroke-width="{LAND_STROKE_WIDTH}" d="{d}"/></svg>\n',
        encoding="utf-8",
    )


def main() -> int:
    if not CONTENT.exists():
        print(f"  ! no talk content at {CONTENT}", file=sys.stderr)
        return 1

    cache = (
        json.loads(GEOCACHE.read_text(encoding="utf-8")) if GEOCACHE.exists() else {}
    )

    # location -> list of talks, so a city visited twice gets one marker.
    places: dict[str, list[dict[str, Any]]] = {}
    missing: Counter[str] = Counter()
    for source in sorted(CONTENT.glob("*.md")):
        meta = parse_frontmatter(source.read_text(encoding="utf-8"))
        location = meta.get("location", "")
        if not location:
            continue
        hit = cache.get(location)
        if not hit:
            missing[location] += 1
            continue
        places.setdefault(location, []).append(
            {
                "title": meta.get("title", source.stem),
                "date": meta.get("date", ""),
                "venue": meta.get("venue", ""),
                "url": f"/talks/{source.stem}.html",
                "lat": hit["latitude"],
                "lon": hit["longitude"],
            },
        )

    if missing:
        # Loud, not silent: an unmapped talk looks identical to a mapped one
        # otherwise, and the count would quietly drift.
        print(
            f"  ! {sum(missing.values())} talk(s) skipped, location not in {GEOCACHE.name}:",
        )
        for location, n in missing.most_common():
            print(f"      {location} x{n}")

    if not places:
        print("  ! no geocoded talks; talk map not written")
        return 0

    # Aggregate by country. A marker per city clutters the map badly, because
    # most of the talks are within a few hundred kilometers of each other: the
    # labels overlap and the dots read as one blob. One marker per country,
    # placed at the mean of its cities' coordinates and scaled by how many talks
    # it holds, is both legible and the more useful summary.
    countries: dict[str, dict[str, Any]] = {}
    for location, talks in places.items():
        country = location.rsplit(",", 1)[-1].strip().strip('"') or "Unknown"
        entry = countries.setdefault(
            country,
            {"talks": [], "cities": {}, "coords": {}},
        )
        entry["coords"][location] = (talks[0]["lat"], talks[0]["lon"])
        for talk in talks:
            entry["talks"].append((talk, location, talks[0]["lat"], talks[0]["lon"]))
            entry["cities"][location] = entry["cities"].get(location, 0) + 1

    ranked = sorted(countries.items(), key=lambda kv: (-len(kv[1]["talks"]), kv[0]))

    # Marker radius grows with the square root of the count, so area is
    # proportional to the number of talks rather than the radius.
    biggest = max((len(c["talks"]) for c in countries.values()), default=1)

    # Marker positions. A country is placed at the mean of its cities'
    # coordinates — each city weighs the same, so one outlier talk does not
    # drag the marker away from where the country actually is.
    discs = []
    for country, entry in ranked:
        lats = [lat for lat, _ in entry["coords"].values()]
        lons = [lon for _, lon in entry["coords"].values()]
        x, y = project(sum(lons) / len(lons), sum(lats) / len(lats))
        discs.append(
            (country, entry, x, y, 7 + 11 * math.sqrt(len(entry["talks"]) / biggest)),
        )

    # Label placement. Most of Europe is within a few hundred kilometers, so
    # markers end up almost on top of each other and a naive "below the dot"
    # label lands one country's text on top of its neighbour's marker. Labels
    # start under their own marker and are pushed down
    # until they clear every marker and every label already placed. Rank order,
    # so the countries with the most talks keep the position nearest the dot.
    #
    # The overlap test compares the SUM of the two half-widths. Testing each
    # label against its own half-width only — which is what this did — is
    # asymmetric and under-detects by up to one label width, which is exactly
    # why Belgium and the Netherlands ended up printed on top of each other.
    labels: list[tuple[float, float, float]] = []
    positioned = []
    for country, entry, x, y, radius in discs:
        half_width = 5.2 * len(country)
        label_y = y + radius + 14
        for step in range(14):
            label_y = y + radius + 14 + step * 15
            clash_label = any(
                abs(px - x) < half_width + pw + 6 and abs(py - label_y) < 14
                for px, py, pw in labels
            )
            clash_dot = any(
                abs(dx - x) < half_width + dr + 4
                and label_y - 6 < dy + dr
                and label_y + 6 > dy - dr
                for _, _, dx, dy, dr in discs
                if not (abs(dx - x) < 0.5 and abs(dy - y) < 0.5)
            )
            if not (clash_label or clash_dot):
                break
        labels.append((x, label_y, half_width))
        positioned.append((country, entry, x, y, radius, label_y))

    markers = []
    for country, entry, x, y, radius, label_y in positioned:
        cities = ", ".join(
            f"{city_name(c)} ({n})" if n > 1 else city_name(c)
            for c, n in sorted(entry["cities"].items())
        )
        # SVG only: an HTML element inside <svg> ends the parser early and
        # silently drops every marker after the first.
        count = len(entry["talks"])
        noun = "talk" if count == 1 else "talks"
        markers.append(
            f'<g class="talk-map__country">'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}">'
            f"<title>{escape(country)} — {count} {noun}: {escape(cities)}</title>"
            f"</circle>"
            f'<text x="{x:.1f}" y="{label_y:.1f}">{escape(country)}'
            f'<tspan class="talk-map__n"> {count}</tspan></text>'
            f"</g>",
        )

    listing = []
    for country, entry in ranked:
        rows = "".join(
            f'<li typeof="Event" resource="https://adafede.github.io{escape(t["url"])}">'
            f'<a href="{escape(t["url"])}" property="url"><span property="name">{escape(t["title"])}</span></a>'
            f'<span class="talk-map__venue">'
            f'<span property="location" typeof="Place"><span property="name">{escape(city_name(location))}</span></span>'
            f"{(' · <span property="superEvent" typeof="Event"><span property="name">' + escape(t['venue']) + '</span></span>') if t['venue'] else ''}"
            f"</span></li>"
            for t, location, _, _ in sorted(
                entry["talks"],
                key=lambda x: x[0]["date"],
                reverse=True,
            )
        )
        cities = ", ".join(city_name(c) for c in sorted(entry["cities"]))
        listing.append(
            f'<details class="talk-map__place"><summary>'
            f'<span class="talk-map__country-name">{escape(country)}</span>'
            f'<span class="talk-map__count">{len(entry["talks"])}</span>'
            f'<span class="talk-map__cities">{escape(cities)}</span>'
            f"</summary><ul>{rows}</ul></details>",
        )

    land = land_paths()
    land_markup = ""
    if land:
        write_land(land)
        land_markup = (
            f'\n  <image href="/talk-map-land.svg" x="0" y="0" '
            f'width="{WIDTH}" height="{HEIGHT}"/>'
        )

    total = sum(len(c["talks"]) for c in countries.values())
    html = f"""<div class="talk-map" role="group" aria-labelledby="talk-map-caption">
{{# Decorative: the list below carries exactly the same information as the
     markers, so a screen reader gains nothing from this being an image. Saying
     so also keeps the contrast checker from measuring text inside a vector
     drawing, which it resolves against no background and always fails. The land
     outline is a separate cached file, drawn under the markers. #}}
<svg viewBox="0 0 {WIDTH} {HEIGHT}" aria-hidden="true" focusable="false">{land_markup}
  {"".join(markers)}
</svg>
<p class="talk-map__legend" id="talk-map-caption">{len(countries)} countries, {total} talks. Marker size grows with the number of talks; the circles carry a tooltip with their cities.</p>
{"".join(listing)}
</div>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"  + {OUT.relative_to(ROOT)} ({len(countries)} countries, {total} talks)")
    if land:
        print(f"  + {LAND_OUT.relative_to(ROOT)} ({len(land) // 1024} KB outline)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
