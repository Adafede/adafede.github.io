"""Build the "areas of expertise" circle packing for the Eleventy build.

Quarto renders this from scripts/utilities/render_circle_packing.py: a SPARQL
query scores topics by where they appear in the Wikidata record — asserted on
the person, used as a main subject of their works, or derived from one — and
circlify packs a circle per topic, sized by that score. The circles link to
their Wikidata items.

The scoring and the layout are ported unchanged, because the scoring *is* the
meaning of the picture: it is why one topic is three times the area of another.
What changes is everything around it:

  * the query runs once, on demand, and its result is committed to
    _cache/expertise.json — the same deal as the talk map's geocodes, so a build
    needs no network and the picture is reproducible;
  * the SVG is inlined as an include rather than embedded in a notebook, so it
    follows the page's own theme switch, which an <img> could not;
  * the drawing is marked decorative and the topics are repeated as a real
    list underneath. Every circle is a link, and an SVG carrying links trips
    axe's nested-interactive rule and makes its text unmeasurable for the
    contrast check — the list carries the same information accessibly and the
    circles stay clickable.

Run: uv run python scripts/site/build_expertise.py [--refresh]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from html import escape
from pathlib import Path
from typing import Any

import circlify as _circlify_module
import matplotlib.colors as mcolors
from circlify import Circle
from cmcrameri import cm

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "_cache" / "expertise.json"
OUT = ROOT / "src" / "eleventy" / "_includes" / "expertise.njk"

QID = "Q97455964"
ENDPOINT = "https://qlever.dev/api/wikidata"
LIMIT = 18
SCALE_POWER = 2.0
ENCLOSURE_R = 300

# Separation between neighbouring circles, in viewBox units.
#
# circlify packs circles tangent to each other: touching, not overlapping. An
# outline drawn on that boundary is centred on it, so each circle's stroke
# extends half its width outward and the two strokes collide across the join.
# That is what makes a packing look like it has overlapping circles — the fills
# never overlap, the borders do.
#
# So the separation is drawn as a gap in the page background instead of a line
# on the boundary: every circle is shrunk by half the gap, leaving half a gap
# either side of it. The circles then cannot touch however the packing comes
# out, and there is nothing for a stroke to collide with.
GAP = 3.0

PREFIXES = """\
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

SCORE_QUERY = (
    PREFIXES
    + f"""
SELECT ?score ?topic ?topicLabel WHERE {{
  {{ SELECT (SUM(?score_) AS ?score) ?topic WHERE {{
    {{ SELECT (64 AS ?score_) ?topic WHERE {{ <http://www.wikidata.org/entity/{QID}>: wdt:P101 ?topic . }} }}
    UNION {{ SELECT (32 AS ?score_) ?topic WHERE {{ ?work wdt:P50 <http://www.wikidata.org/entity/{QID}>: ; wdt:P921 ?topic . }} }}
    UNION {{ SELECT (16 AS ?score_) ?topic WHERE {{ ?work wdt:P50 <http://www.wikidata.org/entity/{QID}>: ; (wdt:P921/wdt:P279) ?topic . }} }}
    UNION {{ SELECT (8 AS ?score_) ?topic WHERE {{ ?work wdt:P50 <http://www.wikidata.org/entity/{QID}>: ; (wdt:P921/wdt:P279/wdt:P279) ?topic . }} }}
    UNION {{ SELECT (32 AS ?score_) ?topic WHERE {{ ?work wdt:P50 <http://www.wikidata.org/entity/{QID}>: ; wdt:P4510 ?topic . }} }}
    UNION {{ SELECT (16 AS ?score_) ?topic WHERE {{ ?work wdt:P50 <http://www.wikidata.org/entity/{QID}>: ; (wdt:P4510/wdt:P279) ?topic . }} }}
    UNION {{ SELECT (8 AS ?score_) ?topic WHERE {{ ?work wdt:P50 <http://www.wikidata.org/entity/{QID}>: ; (wdt:P4510/wdt:P279/wdt:P279) ?topic . }} }}
  }} GROUP BY ?topic }}
  ?topic rdfs:label ?topicLabel .
  FILTER(LANG(?topicLabel) = "en")
}}
ORDER BY DESC(?score)
LIMIT {LIMIT}
"""
)


def qid_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def refresh() -> dict[str, Any]:
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": SCORE_QUERY})
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": "expertise/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        bindings = json.load(response)["results"]["bindings"]
    return {
        "qid": QID,
        "source": ENDPOINT,
        "topics": [
            [
                qid_of(b["topic"]["value"]),
                b["topicLabel"]["value"],
                int(float(b["score"]["value"])),
            ]
            for b in bindings
        ],
    }


def display_label(label: str) -> str:
    """Wikidata returns these lowercase for scientific terms.

    Capitalise the first letter of a label that is entirely lowercase, and
    leave anything already carrying an internal capital alone — that is what
    separates "metabolomics", which wants a capital, from "msConvert", whose
    lowercase m is part of the name.
    """
    if not label:
        return label
    if any(c.isupper() for c in label):
        return label
    return label[:1].upper() + label[1:]


def wrap(label: str, radius: float) -> list[str]:
    """Break a label to fit inside its circle, widest line first."""
    per_line = max(4, int(radius / 5.4))
    lines: list[str] = []
    current = ""
    for word in label.split(" "):
        candidate = f"{current} {word}".strip()
        if len(candidate) > per_line and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def font_size(lines: list[str], radius: float) -> int:
    """Largest size that keeps the block inside the circle."""
    widest = max((len(line) for line in lines), default=1)
    by_height = (radius * 1.35) / (max(1, len(lines)) * 1.2)
    by_width = (radius * 1.7) / (widest * 0.56)
    return max(7, min(26, int(min(by_height, by_width))))


def relative_luminance(rgba) -> float:
    r, g, b = rgba[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def render(data: dict[str, Any]) -> str:
    topics = data["topics"]
    items = [
        {"id": qid, "datum": float(score) ** SCALE_POWER} for qid, _, score in topics
    ]
    meta = {qid: (label, score) for qid, label, score in topics}

    circles = _circlify_module.circlify(
        items,
        show_enclosure=False,
        target_enclosure=Circle(x=0, y=0, r=ENCLOSURE_R),
    )
    circles.sort(key=lambda c: -c.r)  # big circles first: smaller ones nest on top

    centre = ENCLOSURE_R
    # cmcrameri adds this colormap to the module dynamically; indexing the
    # module dictionary avoids a false unknown-attribute diagnostic.
    cmap: mcolors.Colormap = cm.__dict__["batlowK"]

    parts = [
        '<div class="expertise">',
        # Decorative: the list below carries every topic, score and link, so a
        # screen reader gains nothing from an SVG of linked circles — and linked
        # SVG text is exactly what axe and the contrast checker mismeasure.
        (
            f'<svg class="expertise__pack" viewBox="0 0 {centre * 2} {centre * 2}" '
            'aria-hidden="true" focusable="false" '
            'xmlns="http://www.w3.org/2000/svg">'
        ),
    ]

    for index, circle in enumerate(circles):
        # circlify puts the source item in `ex` as a dict in current versions
        # and as a bare id string in older ones; accept either.
        ex = circle.ex
        qid = (
            ex
            if isinstance(ex, str)
            else (ex or {}).get("id", getattr(circle, "id", ""))
        )
        if not isinstance(qid, str) or qid not in meta:
            continue
        label, score = meta[qid]
        text = display_label(label)
        # Drawn radius: the packed radius less half the gap. Clamped so a
        # circle too small to hold the separation still comes out positive.
        cx, cy = centre + circle.x, centre + circle.y
        r = max(1.0, circle.r - GAP / 2)

        rgba = cmap(1 - index / max(1, len(circles) - 1))
        fill = mcolors.to_hex(rgba)
        ink = "#0f172a" if relative_luminance(rgba) > 0.55 else "#ffffff"

        lines = wrap(text, r)
        size = font_size(lines, r)
        leading = size * 1.18
        top = cy - ((len(lines) - 1) * leading) / 2

        # tabindex="-1": the drawing is aria-hidden, and axe (correctly)
        # refuses a hidden subtree that still holds tab stops. Taking the
        # circles out of the tab order costs a keyboard user nothing, because
        # every one of these topics is also a link in the list underneath —
        # which is the accessible copy of this picture in any case.
        parts.append(
            f'<a class="expertise__topic" href="https://www.wikidata.org/wiki/{qid}" '
            f'tabindex="-1" target="_blank" rel="noopener">'
            f"<title>{escape(text)} — score {score}</title>",
        )
        parts.append(
            # The outline colour comes from CSS (--expertise-stroke) rather than
            # being baked in here, because it has to change with the theme and
            # the drawing is generated once for both.
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"/>',
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{top:.1f}" font-size="{size}" fill="{ink}" '
            f'text-anchor="middle" dominant-baseline="central">',
        )
        for i, line in enumerate(lines):
            parts.append(
                f'<tspan x="{cx:.1f}" y="{top + i * leading:.1f}">{escape(line)}</tspan>',
            )
        parts.append("</text></a>")

    parts.append("</svg>")
    # Not a visible column under the figure: the packing is the reading of it.
    # Still in the document and still in the tab order, though, because the
    # circles are aria-hidden and tabindex=-1 — this list is the only way a
    # keyboard reaches these topics at all. It surfaces on focus, the way a
    # skip link does.
    parts.append('<ol class="expertise__list">')
    for qid, label, score in topics:
        parts.append(
            f'<li><a href="https://www.wikidata.org/wiki/{qid}" target="_blank" rel="noopener">'
            f"{escape(display_label(label))}</a>"
            f'<span class="expertise__score">{score}</span></li>',
        )
    parts.append("</ol>")
    parts.append("</div>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-query QLever and rewrite the cache",
    )
    args = parser.parse_args()

    if args.refresh:
        try:
            data = refresh()
        except Exception as exc:  # noqa: BLE001 - report, then fall back to the cache
            print(f"  ! refresh failed ({exc}); drawing from the existing cache")
            if not CACHE.exists():
                print("  ! no cache to fall back on", file=sys.stderr)
                return 1
            data = json.loads(CACHE.read_text("utf-8"))
        else:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                "utf-8",
            )
            print(f"  + _cache/expertise.json ({len(data['topics'])} topics)")
    elif CACHE.exists():
        data = json.loads(CACHE.read_text("utf-8"))
    else:
        print(f"  ! no cache at {CACHE}; run with --refresh", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(data) + "\n", "utf-8")
    print(f"  + src/eleventy/_includes/expertise.njk ({len(data['topics'])} circles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
