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
an equirectangular projection over a Natural Earth land outline, and the whole
thing is one inline SVG with no runtime dependencies. Talks whose location is
not in the geocode cache are reported and skipped rather than silently dropped.

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
import sys
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "src" / "content" / "talks"
GEOCACHE = ROOT / "_cache" / "geocache.json"
LAND = ROOT / "data" / "world-land.json"
OUT = ROOT / "src" / "eleventy" / "_includes" / "talk-map.njk"

# Equirectangular. Cropped tightly to Europe: at a wider extent every
# talk sits in one overlapping cluster near the Alps and the labels collide.
WIDTH, HEIGHT = 960, 480
LON_MIN, LON_MAX = -11.0, 24.0
LAT_MIN, LAT_MAX = 35.0, 56.0


def parse_frontmatter(raw: str) -> dict:
    """Minimal YAML frontmatter reader.

    The talk files only use flat scalars and inline lists, so pulling in a YAML
    parser here would add a dependency for no benefit.
    """
    if not raw.startswith("---"):
        return {}
    end = raw.find("\n---", 3)
    if end == -1:
        return {}
    data: dict = {}
    for line in raw[3:end].splitlines():
        if not line.strip() or line.startswith((" ", "\t", "-")):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            data[key.strip()] = [
                v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()
            ]
        else:
            data[key.strip()] = value.strip("'\"")
    return data


def city_name(location: str) -> str:
    """The city alone, without the country the heading above it already names."""
    return location.rsplit(",", 1)[0].strip().strip('"')


def project(lon: float, lat: float) -> tuple[float, float]:
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * WIDTH
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * HEIGHT
    return x, y


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
                if not any(0 <= x <= WIDTH and 0 <= y <= HEIGHT for x, y in points):
                    continue  # Entirely outside the crop.
                d = "M" + " ".join(f"{x:.1f},{y:.1f}" for x, y in points) + "Z"
                paths.append(d)
    return "".join(paths)


def main() -> int:
    if not CONTENT.exists():
        print(f"  ! no talk content at {CONTENT}", file=sys.stderr)
        return 1

    cache = (
        json.loads(GEOCACHE.read_text(encoding="utf-8")) if GEOCACHE.exists() else {}
    )

    # location -> list of talks, so a city visited twice gets one marker.
    places: dict[str, list[dict]] = {}
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
    # most of the talks are within a few hundred kilometres of each other: the
    # labels overlap and the dots read as one blob. One marker per country,
    # placed at the mean of its talk coordinates and scaled by how many talks it
    # holds, is both legible and the more useful summary.
    countries: dict[str, dict] = {}
    for location, talks in places.items():
        country = location.rsplit(",", 1)[-1].strip().strip('"') or "Unknown"
        entry = countries.setdefault(country, {"talks": [], "cities": {}})
        for talk in talks:
            entry["talks"].append((talk, location, talks[0]["lat"], talks[0]["lon"]))
            entry["cities"][location] = entry["cities"].get(location, 0) + 1

    ranked = sorted(countries.items(), key=lambda kv: (-len(kv[1]["talks"]), kv[0]))

    # Marker radius grows with the square root of the count, so area is
    # proportional to the number of talks rather than the radius.
    biggest = max((len(c["talks"]) for c in countries.values()), default=1)

    # Label placement. Most of Europe is within a few hundred kilometres, so
    # markers end up almost on top of each other and a naive "below the dot"
    # label lands one country's text on top of its neighbour's marker. Labels
    # are therefore pushed down until they clear every other marker disc and
    # every label already placed. Rank order, so the countries with the most
    # talks keep the position closest to their own marker.
    discs = []
    for country, entry in ranked:
        lats = [t[2] for t in entry["talks"]]
        lons = [t[3] for t in entry["talks"]]
        x, y = project(sum(lons) / len(lons), sum(lats) / len(lats))
        discs.append(
            (country, entry, x, y, 7 + 11 * math.sqrt(len(entry["talks"]) / biggest)),
        )

    # Label placement. Labels start under their own marker and are pushed down
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
        markers.append(
            f'<g class="talk-map__country">'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}">'
            f"<title>{escape(country)} — {len(entry['talks'])} talk(s): {escape(cities)}</title>"
            f"</circle>"
            f'<text x="{x:.1f}" y="{label_y:.1f}">{escape(country)}'
            f'<tspan class="talk-map__n"> {len(entry["talks"])}</tspan></text>'
            f"</g>",
        )

    listing = []
    for country, entry in ranked:
        rows = "".join(
            f'<li><a href="{escape(t["url"])}">{escape(t["title"])}</a>'
            f'<span class="talk-map__venue">{escape(city_name(location))}'
            f"{' · ' + escape(t['venue']) if t['venue'] else ''}</span></li>"
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

    total = sum(len(c["talks"]) for c in countries.values())
    html = f"""<div class="talk-map" role="group" aria-labelledby="talk-map-caption">
<!-- Decorative: the list below carries exactly the same information as the
     markers, so a screen reader gains nothing from this being an image. Saying
     so also keeps the contrast checker from measuring text inside a vector
     drawing, which it resolves against no background and always fails. -->
<svg viewBox="0 0 {WIDTH} {HEIGHT}" aria-hidden="true" focusable="false">
  <path class="talk-map__land" d="{land_paths()}"/>
  {"".join(markers)}
</svg>
<p class="talk-map__legend" id="talk-map-caption">{len(countries)} countries, {total} talks. Marker size grows with the number of talks; the circles carry a tooltip with their cities.</p>
{"".join(listing)}
</div>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"  + {OUT.relative_to(ROOT)} ({len(countries)} countries, {total} talks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
